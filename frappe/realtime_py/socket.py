# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Typed Socket wrapper passed to handlers.

Thin, typed facade over the python-socketio server bound to one sid + namespace,
plus the session stored at connect time. Read-only session fields + emit/room
helpers. ``has_permission`` is the HTTP check (delegated to the web process); the
``frappe_request`` callable that performs it is attached by auth.py at connect, so
the wrapper carries no HTTP/secret logic itself.
"""

from collections.abc import Callable

# Session keys stored on the python-socketio session at connect (see auth.py).
# frappe_request is the authenticated GET helper toward the web process.


class Socket:
	def __init__(
		self,
		sio,
		sid: str,
		namespace: str,
		session: dict,
		frappe_request: Callable[..., dict] | None = None,
	):
		self._sio = sio
		self.sid = sid
		self.namespace = namespace
		self._session = session
		self._frappe_request = frappe_request

	@property
	def site(self) -> str:
		return self._session["site"]

	@property
	def user(self) -> str:
		return self._session["user"]

	@property
	def user_type(self) -> str:
		return self._session.get("user_type", "")

	@property
	def installed_apps(self) -> list[str]:
		return self._session.get("installed_apps", [])

	def join(self, room: str) -> None:
		self._sio.enter_room(self.sid, room, namespace=self.namespace)

	def leave(self, room: str) -> None:
		self._sio.leave_room(self.sid, room, namespace=self.namespace)

	def emit(self, event: str, data: object | None = None, room: str | None = None) -> None:
		"""Emit to a room, or to this client (default)."""
		self._sio.emit(event, data, to=room or self.sid, namespace=self.namespace)

	def get(self, key: str, default: object = None) -> object:
		"""Read a value from this socket's session."""
		return self._session.get(key, default)

	def set(self, key: str, value: object) -> None:
		"""Persist a value onto this socket's session."""
		self._session[key] = value
		self._sio.save_session(self.sid, self._session, namespace=self.namespace)

	def participants(self, room: str) -> list[str]:
		"""sids currently in ``room`` of this namespace."""
		sids = []
		for item in self._sio.manager.get_participants(self.namespace, room):
			sids.append(item[0] if isinstance(item, tuple) else item)
		return sids

	def user_of(self, sid: str) -> str | None:
		"""User stored on another socket's session, or None if it has none."""
		try:
			return self._sio.get_session(sid, namespace=self.namespace).get("user")
		except KeyError:
			return None

	def has_permission(self, doctype: str, name: str | None = None) -> bool:
		"""HTTP permission check against the web process (frappe.realtime.has_permission).

		Mirrors the Node handler: no DB in the realtime process. For in-process
		checks use frappe.has_permission inside a frappe_context=True handler."""
		if self._frappe_request is None:
			raise RuntimeError("Socket.has_permission called without an attached frappe_request")
		try:
			body = self._frappe_request(
				"/api/method/frappe.realtime.has_permission",
				{"doctype": doctype, "name": name or ""},
			)
		except Exception:
			return False
		return bool(body.get("message"))
