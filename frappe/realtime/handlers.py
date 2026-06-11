# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

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
def on_connect(socket: Socket) -> None:
	socket.join(user_room(socket.user))
	socket.join(WEBSITE_ROOM)
	if socket.user_type == "System User":
		socket.join(SITE_ROOM)


@realtime.on("ping", allow_guest=True)
def ping(socket: Socket) -> None:
	socket.emit("pong")


@realtime.on("doctype_subscribe", allow_guest=True)
def doctype_subscribe(socket: Socket, doctype: str) -> None:
	if socket.has_permission(doctype):
		socket.join(doctype_room(doctype))


@realtime.on("doctype_unsubscribe", allow_guest=True)
def doctype_unsubscribe(socket: Socket, doctype: str) -> None:
	socket.leave(doctype_room(doctype))


@realtime.on("task_subscribe", allow_guest=True)
def task_subscribe(socket: Socket, task_id: str) -> None:
	socket.join(task_room(task_id))


@realtime.on("task_unsubscribe", allow_guest=True)
def task_unsubscribe(socket: Socket, task_id: str) -> None:
	socket.leave(task_room(task_id))


@realtime.on("progress_subscribe", allow_guest=True)
def progress_subscribe(socket: Socket, task_id: str) -> None:
	socket.join(task_room(task_id))


@realtime.on("doc_subscribe", allow_guest=True)
def doc_subscribe(socket: Socket, doctype: str, docname: str) -> None:
	if socket.has_permission(doctype, docname):
		socket.join(doc_room(doctype, docname))


@realtime.on("doc_unsubscribe", allow_guest=True)
def doc_unsubscribe(socket: Socket, doctype: str, docname: str) -> None:
	socket.leave(doc_room(doctype, docname))


@realtime.on("doc_open", allow_guest=True)
def doc_open(socket: Socket, doctype: str, docname: str) -> None:
	if not socket.has_permission(doctype, docname):
		return
	socket.join(open_doc_room(doctype, docname))

	tracked = socket.get("subscribed_documents", [])
	pair = [doctype, docname]
	if pair not in tracked:
		tracked.append(pair)
		socket.set("subscribed_documents", tracked)
	notify_doc_viewers(socket, doctype, docname)


@realtime.on("doc_close", allow_guest=True)
def doc_close(socket: Socket, doctype: str, docname: str) -> None:
	socket.leave(open_doc_room(doctype, docname))
	# Fix Node bug (handlers.js:91-93): the filter callback never returned, so the
	# pair was never dropped. Actually remove it here.
	tracked = socket.get("subscribed_documents", [])
	tracked = [pair for pair in tracked if not (pair[0] == doctype and pair[1] == docname)]
	socket.set("subscribed_documents", tracked)
	notify_doc_viewers(socket, doctype, docname)


@realtime.on("disconnect", allow_guest=True)
def on_disconnect(socket: Socket) -> None:
	for doctype, docname in socket.get("subscribed_documents", []):
		notify_doc_viewers(socket, doctype, docname)


def notify_doc_viewers(socket: Socket, doctype: str, docname: str) -> None:
	"""Emit doc_viewers to everyone in the open-doc room. Port of notify_subscribed_doc_users."""
	if not (doctype and docname):
		return
	room = open_doc_room(doctype, docname)
	users = [u for u in (socket.user_of(sid) for sid in socket.participants(room)) if u]
	# Don't send an update to a lone viewer about themselves.
	if len(users) == 1 and users[0] == socket.user:
		return
	socket.emit(
		"doc_viewers",
		{"doctype": doctype, "docname": docname, "users": list(dict.fromkeys(users))},
		room=room,
	)


@realtime.on("open_in_editor")
def open_in_editor(socket: Socket, data: object) -> None:
	"""Dev-only: forward esbuild "open in editor" to the redis open_in_editor channel."""
	config = get_config()
	if not config.developer_mode:
		return

	import redis

	client = redis.from_url(config.redis_queue)
	try:
		client.publish("open_in_editor", json.dumps(data))
	finally:
		client.close()
