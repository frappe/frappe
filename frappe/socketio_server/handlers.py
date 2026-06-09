"""
PROTOTYPE: port of apps/frappe/realtime/handlers.js to python-socketio.

In a real impl `_check_permission` is a direct frappe.has_permission call —
but that needs a properly-bound site/session context which we don't have in
this prototype's async path (see auth.py). For now permission checks are
permissive when FRAPPE_SOCKETIO_DEBUG_SKIP_AUTH=1.
"""

import os

WEBSITE_ROOM = "website"
SITE_ROOM = "all"


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
	async def _connect(sid, environ, auth):
		# Auth + room setup is driven from server.on_site_connect; this is
		# just here so the namespace exists. server.py calls authenticate()
		# then enters the per-user rooms below via _post_auth_join.
		from frappe.socketio_server.server import on_site_connect

		await on_site_connect(sid, environ, auth, namespace)
		session = await sio.get_session(sid, namespace=namespace)
		await sio.enter_room(sid, _user_room(session["user"]), namespace=namespace)
		await sio.enter_room(sid, WEBSITE_ROOM, namespace=namespace)
		if session.get("user_type") == "System User":
			await sio.enter_room(sid, SITE_ROOM, namespace=namespace)

	@sio.on("ping", namespace=namespace)
	async def _ping(sid):
		await sio.emit("pong", to=sid, namespace=namespace)

	@sio.on("doctype_subscribe", namespace=namespace)
	async def _doctype_subscribe(sid, doctype):
		if await _check_permission(sid, namespace, doctype):
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
		if await _check_permission(sid, namespace, doctype, docname):
			await sio.enter_room(sid, _doc_room(doctype, docname), namespace=namespace)

	@sio.on("doc_unsubscribe", namespace=namespace)
	async def _doc_unsubscribe(sid, doctype, docname):
		await sio.leave_room(sid, _doc_room(doctype, docname), namespace=namespace)

	@sio.on("doc_open", namespace=namespace)
	async def _doc_open(sid, doctype, docname):
		if not await _check_permission(sid, namespace, doctype, docname):
			return
		room = _open_doc_room(doctype, docname)
		await sio.enter_room(sid, room, namespace=namespace)
		session = await sio.get_session(sid, namespace=namespace)
		session.setdefault("open_docs", []).append((doctype, docname))
		await sio.save_session(sid, session, namespace=namespace)
		await _notify_viewers(sio, namespace, doctype, docname)

	@sio.on("doc_close", namespace=namespace)
	async def _doc_close(sid, doctype, docname):
		room = _open_doc_room(doctype, docname)
		await sio.leave_room(sid, room, namespace=namespace)
		session = await sio.get_session(sid, namespace=namespace)
		session["open_docs"] = [t for t in session.get("open_docs", []) if t != (doctype, docname)]
		await sio.save_session(sid, session, namespace=namespace)
		await _notify_viewers(sio, namespace, doctype, docname)

	@sio.on("disconnect", namespace=namespace)
	async def _disconnect(sid):
		session = await sio.get_session(sid, namespace=namespace)
		for doctype, docname in session.get("open_docs", []):
			await _notify_viewers(sio, namespace, doctype, docname, exclude_sid=sid)


# --- helpers ----------------------------------------------------------------
async def _check_permission(sio, namespace, doctype, docname=None) -> bool:
	"""TODO: route through a thread-pool wrapper of frappe.has_permission with
	a properly-bound site/user context, or fall back to an HTTP callback like
	the JS version. Permissive in debug-skip-auth mode for smoke testing."""
	if os.environ.get("FRAPPE_SOCKETIO_DEBUG_SKIP_AUTH") == "1":
		return True
	return False


async def _notify_viewers(sio, namespace, doctype, docname, exclude_sid=None):
	room = _open_doc_room(doctype, docname)
	members = sio.manager.get_participants(namespace, room)
	users = []
	for sid, _ in members:
		if sid == exclude_sid:
			continue
		session = await sio.get_session(sid, namespace=namespace)
		users.append(session["user"])
	users = sorted(set(users))
	if len(users) <= 1:
		return
	await sio.emit(
		"doc_viewers",
		{"doctype": doctype, "docname": docname, "users": users},
		room=room,
		namespace=namespace,
	)
