# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


from contextlib import suppress
from typing import TYPE_CHECKING

import redis

import frappe
from frappe.utils.data import cstr

if TYPE_CHECKING:
	from frappe.realtime.registry import realtime as realtime
	from frappe.realtime.socket import Socket as Socket


def publish_progress(percent, title=None, doctype=None, docname=None, description=None, task_id=None):
	publish_realtime(
		"progress",
		{"percent": percent, "title": title, "description": description},
		user=None if doctype and docname else frappe.session.user,
		doctype=doctype,
		docname=docname,
		task_id=task_id,
	)


def publish_realtime(
	event: str | None = None,
	message: dict | None = None,
	room: str | None = None,
	user: str | None = None,
	doctype: str | None = None,
	docname: str | None = None,
	task_id: str | None = None,
	after_commit: bool = False,
):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc. that will be handled by the client (default is `task_progress` if within task or `global`)
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname
	:param after_commit: (default False) will emit after current transaction is committed"""
	if message is None:
		message = {}

	if not task_id and hasattr(frappe.local, "task_id"):
		task_id = frappe.local.task_id

	if event is None:
		event = "task_progress" if task_id else "global"
	elif event == "msgprint" and not user:
		user = frappe.session.user
	elif event == "list_update":
		doctype = doctype or message.get("doctype")
		room = get_doctype_room(doctype)
	elif event == "docinfo_update":
		room = get_doc_room(doctype, docname)

	if not room:
		if task_id:
			after_commit = False
			if "task_id" not in message:
				message["task_id"] = task_id
			room = get_task_progress_room(task_id)
		elif user:
			# transmit to specific user: System, Website or Guest
			room = get_user_room(user)
		elif doctype and docname:
			room = get_doc_room(doctype, docname)
		else:
			# This will be broadcasted to all Desk users
			room = get_site_room()

	if after_commit:
		if not hasattr(frappe.local, "_realtime_log"):
			frappe.local._realtime_log = []
			frappe.db.after_commit.add(flush_realtime_log)
			frappe.db.after_rollback.add(clear_realtime_log)

		params = [event, message, room]
		if params not in frappe.local._realtime_log:
			frappe.local._realtime_log.append(params)
	else:
		emit_via_redis(event, message, room)


def flush_realtime_log():
	if not hasattr(frappe.local, "_realtime_log"):
		return
	for args in frappe.local._realtime_log:
		frappe.realtime.emit_via_redis(*args)

	clear_realtime_log()


def clear_realtime_log():
	if hasattr(frappe.local, "_realtime_log"):
		del frappe.local._realtime_log


def emit_via_redis(event, message, room):
	"""Publish real-time updates via redis

	:param event: Event name, like `task_progress` etc.
	:param message: JSON message object. For async must contain `task_id`
	:param room: name of the room"""
	from frappe.utils.background_jobs import get_redis_connection_without_auth

	with suppress(redis.exceptions.ConnectionError):
		r = get_redis_connection_without_auth()
		r.publish(
			"events",
			frappe.as_json(
				{"event": event, "message": message, "room": room, "namespace": frappe.local.site}
			),
		)


@frappe.whitelist(allow_guest=True)  # nosemgrep
def has_permission(doctype: str, name: str, ptype: str = "read") -> bool:
	frappe.has_permission(doctype, doc=name, ptype=ptype, throw=True)
	return True


SOCKETIO_SECRET_KEY = "socketio_auth_secret"


def get_socketio_secret():
	"""Generate socket.io secret and store in redis"""

	from frappe.utils.background_jobs import get_redis_connection_without_auth

	r = get_redis_connection_without_auth()
	secret = r.get(SOCKETIO_SECRET_KEY)
	if secret:
		return secret.decode()

	secret = frappe.generate_hash(length=32)
	r.set(SOCKETIO_SECRET_KEY, secret)
	return secret


@frappe.whitelist(allow_guest=True)
def get_user_info():
	user_type = frappe.session.data.user_type
	trusted_secret = get_socketio_secret()
	provided_secret = frappe.get_request_header("X-Frappe-Socket-Secret")
	if trusted_secret != provided_secret:
		return {}
	# For requests with Bearer tokens, user_type is not set in the session data
	if not user_type:
		user_type = frappe.get_cached_value("User", frappe.session.user, "user_type")
	return {
		"user": frappe.session.user,
		"user_type": user_type,
		"installed_apps": frappe.get_installed_apps(),
	}


def get_doctype_room(doctype):
	return f"doctype:{doctype}"


def get_doc_room(doctype, docname):
	return f"doc:{doctype}/{cstr(docname)}"


def get_user_room(user):
	return f"user:{user}"


def get_site_room():
	return "all"


def get_task_progress_room(task_id):
	return f"task_progress:{task_id}"


def get_website_room():
	return "website"


# Named publisher helpers — sugar over publish_realtime. No new wire behavior:
# each maps to the same room publish_realtime already produces. publish_realtime
# itself is unchanged.


def publish_to_user(user: str, event: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish to a specific user's room (user:{user})."""
	publish_realtime(event, message, user=user, after_commit=after_commit)


def publish_to_doc(
	doctype: str, docname: str, event: str, message: dict | None = None, *, after_commit: bool = False
):
	"""Publish to a document's room (doc:{doctype}/{docname})."""
	publish_realtime(event, message, doctype=doctype, docname=docname, after_commit=after_commit)


def publish_to_doctype(doctype: str, event: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish to a doctype's room (doctype:{doctype})."""
	publish_realtime(event, message, room=get_doctype_room(doctype), after_commit=after_commit)


def publish_task_progress(task_id: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish task progress to task_progress:{task_id}."""
	publish_realtime(message=message, task_id=task_id, after_commit=after_commit)


def publish_to_website(event: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish to the website room."""
	publish_realtime(event, message, room=get_website_room(), after_commit=after_commit)


def publish_to_all(event: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish to the site "all" room (System Users of THIS site).

	NOTE: this is the site-scoped room, NOT the cross-site no-room broadcast that
	build events use."""
	publish_realtime(event, message, room=get_site_room(), after_commit=after_commit)


def publish_to_room(room: str, event: str, message: dict | None = None, *, after_commit: bool = False):
	"""Publish to an arbitrary room."""
	publish_realtime(event, message, room=room, after_commit=after_commit)


# Handler-authoring surface, exposed lazily so the publish helpers above stay
# import-light. ``Socket`` pulls in the server stack (socketio, via auth); resolving
# it only on access keeps ``from frappe.realtime import publish_realtime`` (web
# process) from importing socketio/gevent.
def __getattr__(name: str) -> object:
	if name == "realtime":
		from frappe.realtime.registry import realtime

		return realtime
	if name == "Socket":
		from frappe.realtime.socket import Socket

		return Socket
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
