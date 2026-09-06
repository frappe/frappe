# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import redis.asyncio

from frappe.realtime import Socket, realtime
from frappe.realtime.config import get_config

WEBSITE_ROOM = "website"
SITE_ROOM = "all"


def user_room(user: str) -> str:
	return f"user:{user}"


def doctype_room(doctype: str) -> str:
	return f"doctype:{doctype}"


def doc_room(doctype: str, docname: str) -> str:
	return f"doc:{doctype}/{docname}"


def task_room(task_id: str) -> str:
	return f"task_progress:{task_id}"


def open_doc_room(doctype: str, docname: str) -> str:
	return f"open_doc:{doctype}/{docname}"


@realtime.on("connect", allow_guest=True)
async def on_connect(socket: Socket) -> None:
	await socket.join(user_room(socket.user))
	await socket.join(WEBSITE_ROOM)
	if socket.user_type == "System User":
		await socket.join(SITE_ROOM)


@realtime.on("ping", allow_guest=True)
async def ping(socket: Socket) -> None:
	await socket.emit("pong")


@realtime.on("doctype_subscribe", allow_guest=True)
async def doctype_subscribe(socket: Socket, doctype: str) -> None:
	if await socket.has_permission(doctype):
		await socket.join(doctype_room(doctype))


@realtime.on("doctype_unsubscribe", allow_guest=True)
async def doctype_unsubscribe(socket: Socket, doctype: str) -> None:
	await socket.leave(doctype_room(doctype))


@realtime.on("task_subscribe", allow_guest=True)
async def task_subscribe(socket: Socket, task_id: str) -> None:
	await socket.join(task_room(task_id))


@realtime.on("task_unsubscribe", allow_guest=True)
async def task_unsubscribe(socket: Socket, task_id: str) -> None:
	await socket.leave(task_room(task_id))


@realtime.on("progress_subscribe", allow_guest=True)
async def progress_subscribe(socket: Socket, task_id: str) -> None:
	await socket.join(task_room(task_id))


@realtime.on("doc_subscribe", allow_guest=True)
async def doc_subscribe(socket: Socket, doctype: str, docname: str) -> None:
	if await socket.has_permission(doctype, docname):
		await socket.join(doc_room(doctype, docname))


@realtime.on("doc_unsubscribe", allow_guest=True)
async def doc_unsubscribe(socket: Socket, doctype: str, docname: str) -> None:
	await socket.leave(doc_room(doctype, docname))


@realtime.on("doc_open", allow_guest=True)
async def doc_open(socket: Socket, doctype: str, docname: str) -> None:
	if not await socket.has_permission(doctype, docname):
		return
	await socket.join(open_doc_room(doctype, docname))

	tracked = socket.get("subscribed_documents", [])
	pair = [doctype, docname]
	if pair not in tracked:
		tracked.append(pair)
		await socket.set("subscribed_documents", tracked)
	await notify_doc_viewers(socket, doctype, docname)


@realtime.on("doc_close", allow_guest=True)
async def doc_close(socket: Socket, doctype: str, docname: str) -> None:
	await socket.leave(open_doc_room(doctype, docname))
	# Fix Node bug (handlers.js:91-93): the filter callback never returned, so the
	# pair was never dropped. Actually remove it here.
	tracked = socket.get("subscribed_documents", [])
	tracked = [pair for pair in tracked if not (pair[0] == doctype and pair[1] == docname)]
	await socket.set("subscribed_documents", tracked)
	await notify_doc_viewers(socket, doctype, docname)


@realtime.on("disconnect", allow_guest=True)
async def on_disconnect(socket: Socket) -> None:
	for doctype, docname in socket.get("subscribed_documents", []):
		await notify_doc_viewers(socket, doctype, docname)


async def notify_doc_viewers(socket: Socket, doctype: str, docname: str) -> None:
	"""Emit doc_viewers to everyone in the open-doc room. Port of notify_subscribed_doc_users."""
	if not (doctype and docname):
		return
	room = open_doc_room(doctype, docname)
	users = []
	for sid in socket.participants(room):
		user = await socket.user_of(sid)
		if user:
			users.append(user)
	# Don't send an update to a lone viewer about themselves.
	if len(users) == 1 and users[0] == socket.user:
		return
	await socket.emit(
		"doc_viewers",
		{"doctype": doctype, "docname": docname, "users": list(dict.fromkeys(users))},
		room=room,
	)


@realtime.on("open_in_editor")
async def open_in_editor(socket: Socket, data: object) -> None:
	"""Dev-only: forward esbuild "open in editor" to the redis open_in_editor channel."""
	config = get_config()
	if not config.developer_mode:
		return

	client = redis.asyncio.from_url(config.redis_queue)
	try:
		await client.publish("open_in_editor", json.dumps(data))
	finally:
		await client.aclose()
