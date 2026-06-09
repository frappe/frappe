"""Per-namespace event handlers — port of apps/frappe/realtime/handlers.js.

python-socketio registers handlers per *namespace* (one per site), not per
socket like the Node implementation, so per-connection state (user, open
docs, credentials) lives in the socket session saved at connect time.
"""

import importlib
import importlib.util
import json
import logging

import redis.asyncio as aioredis
import socketio

from frappe.socketio_server import redis_url
from frappe.socketio_server.auth import authenticate, check_permission

logger = logging.getLogger("frappe.socketio")

WEBSITE_ROOM = "website"
SITE_ROOM = "all"

# (app, namespace) pairs whose realtime handlers are already registered
_registered_apps: set[tuple[str, str]] = set()
_redis_publisher: aioredis.Redis | None = None


def _doc_room(doctype, docname):
	return f"doc:{doctype}/{docname}"


def _open_doc_room(doctype, docname):
	return f"open_doc:{doctype}/{docname}"


def _user_room(user):
	return f"user:{user}"


def _doctype_room(doctype):
	return f"doctype:{doctype}"


def _task_room(task_id):
	return f"task_progress:{task_id}"


def register_frappe_handlers(sio, namespace: str):
	"""Attach all Frappe event handlers to a dynamically-created namespace.

	Called once per site, the first time a client connects to /{site}.
	"""

	@sio.on("connect", namespace=namespace)
	async def _connect(sid, environ, auth=None):
		ok, ctx = await authenticate(environ, namespace)
		if not ok:
			raise socketio.exceptions.ConnectionRefusedError(ctx)  # ctx is the error message

		await sio.save_session(sid, ctx, namespace=namespace)
		await sio.enter_room(sid, _user_room(ctx["user"]), namespace=namespace)
		await sio.enter_room(sid, WEBSITE_ROOM, namespace=namespace)
		if ctx.get("user_type") == "System User":
			await sio.enter_room(sid, SITE_ROOM, namespace=namespace)

		_register_app_handlers(sio, namespace, ctx["installed_apps"])

	@sio.on("ping", namespace=namespace)
	async def _ping(sid):
		await sio.emit("pong", to=sid, namespace=namespace)

	@sio.on("doctype_subscribe", namespace=namespace)
	async def _doctype_subscribe(sid, doctype):
		ctx = await sio.get_session(sid, namespace=namespace)
		if await check_permission(ctx, doctype):
			await sio.enter_room(sid, _doctype_room(doctype), namespace=namespace)

	@sio.on("doctype_unsubscribe", namespace=namespace)
	async def _doctype_unsubscribe(sid, doctype):
		await sio.leave_room(sid, _doctype_room(doctype), namespace=namespace)

	@sio.on("task_subscribe", namespace=namespace)
	async def _task_subscribe(sid, task_id):
		await sio.enter_room(sid, _task_room(task_id), namespace=namespace)

	@sio.on("task_unsubscribe", namespace=namespace)
	async def _task_unsubscribe(sid, task_id):
		await sio.leave_room(sid, _task_room(task_id), namespace=namespace)

	@sio.on("progress_subscribe", namespace=namespace)
	async def _progress_subscribe(sid, task_id):
		await sio.enter_room(sid, _task_room(task_id), namespace=namespace)

	@sio.on("doc_subscribe", namespace=namespace)
	async def _doc_subscribe(sid, doctype, docname):
		ctx = await sio.get_session(sid, namespace=namespace)
		if await check_permission(ctx, doctype, docname):
			await sio.enter_room(sid, _doc_room(doctype, docname), namespace=namespace)

	@sio.on("doc_unsubscribe", namespace=namespace)
	async def _doc_unsubscribe(sid, doctype, docname):
		await sio.leave_room(sid, _doc_room(doctype, docname), namespace=namespace)

	@sio.on("doc_open", namespace=namespace)
	async def _doc_open(sid, doctype, docname):
		ctx = await sio.get_session(sid, namespace=namespace)
		if not await check_permission(ctx, doctype, docname):
			return
		await sio.enter_room(sid, _open_doc_room(doctype, docname), namespace=namespace)
		ctx.setdefault("open_docs", []).append((doctype, docname))
		await sio.save_session(sid, ctx, namespace=namespace)
		await _notify_viewers(sio, namespace, doctype, docname, current_user=ctx["user"])

	@sio.on("doc_close", namespace=namespace)
	async def _doc_close(sid, doctype, docname):
		await sio.leave_room(sid, _open_doc_room(doctype, docname), namespace=namespace)
		ctx = await sio.get_session(sid, namespace=namespace)
		ctx["open_docs"] = [entry for entry in ctx.get("open_docs", []) if entry != (doctype, docname)]
		await sio.save_session(sid, ctx, namespace=namespace)
		await _notify_viewers(sio, namespace, doctype, docname, current_user=ctx["user"])

	@sio.on("open_in_editor", namespace=namespace)
	async def _open_in_editor(sid, data):
		# Republish for the esbuild watcher ("open in editor" on build error)
		await _publish_to_redis("open_in_editor", data)

	@sio.on("disconnect", namespace=namespace)
	async def _disconnect(sid, reason=None):
		# The socket is still in its rooms here (removed after this handler
		# runs) — exclude it explicitly to mirror the Node implementation,
		# where "disconnect" fires after rooms are left.
		ctx = await sio.get_session(sid, namespace=namespace)
		for doctype, docname in ctx.get("open_docs", []):
			await _notify_viewers(sio, namespace, doctype, docname, current_user=ctx["user"], exclude_sid=sid)


def _register_app_handlers(sio, namespace: str, installed_apps: list[str]):
	"""Per-app realtime handlers, discovered by import instead of the Node
	implementation's filesystem walk over apps/{app}/realtime/handlers.js.

	An app opts in by shipping a `{app}.realtime_handlers` module with a
	`register(sio, namespace)` callable. Unlike the Node version it is invoked
	once per namespace (site), not once per socket — per-connection state
	belongs in the socket session.
	"""
	for app in installed_apps:
		if app == "frappe" or (app, namespace) in _registered_apps:
			continue
		_registered_apps.add((app, namespace))
		try:
			if importlib.util.find_spec(f"{app}.realtime_handlers") is None:
				continue
			module = importlib.import_module(f"{app}.realtime_handlers")
			register = getattr(module, "register", None)
			if register:
				register(sio, namespace)
		except Exception:
			logger.warning("failed to setup realtime handlers from %s", app, exc_info=True)


async def _publish_to_redis(channel: str, data):
	global _redis_publisher
	if _redis_publisher is None:
		_redis_publisher = aioredis.from_url(redis_url())
	await _redis_publisher.publish(channel, json.dumps(data))


async def _notify_viewers(sio, namespace, doctype, docname, current_user, exclude_sid=None):
	"""Tell everyone with this document open who is currently viewing it."""
	room = _open_doc_room(doctype, docname)
	users = []
	for member_sid, _ in sio.manager.get_participants(namespace, room):
		if member_sid == exclude_sid:
			continue
		session = await sio.get_session(member_sid, namespace=namespace)
		users.append(session["user"])

	# don't send update to self. meaningless.
	if len(users) == 1 and users[0] == current_user:
		return

	await sio.emit(
		"doc_viewers",
		{"doctype": doctype, "docname": docname, "users": sorted(set(users))},
		room=room,
		namespace=namespace,
	)
