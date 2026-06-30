# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING

from frappe.realtime.auth import Session

if TYPE_CHECKING:
	from socketio.server import Server as SocketIOServer


class Socket:
	"""Typed Socket wrapper passed to handlers.

	Thin facade over the python-socketio server bound to one sid + namespace,
	plus the authenticated Session stored at connect. Read-only identity fields
	and emit/room helpers; identity + has_permission delegate to the Session, so
	the wrapper carries no auth/HTTP logic itself.
	"""

	def __init__(self, sio: SocketIOServer, sid: str, namespace: str, session: Session):
		self._sio = sio
		self.sid = sid
		self.namespace = namespace
		self._session = session

	@property
	def site(self) -> str:
		return self._session.site

	@property
	def user(self) -> str:
		return self._session.user

	@property
	def user_type(self) -> str:
		return self._session.user_type or ""

	@property
	def installed_apps(self) -> list[str]:
		return self._session.installed_apps

	def _connected(self) -> bool:
		"""Is this sid still attached to its namespace?

		Events dispatch in their own greenlet (async_handlers), and a handler can
		yield the gevent hub mid-body (e.g. has_permission does an HTTP call). The
		client may disconnect in that window, after which the namespace is gone from
		the manager — enter_room then raises "sid is not connected to requested
		namespace" and save_session raises KeyError (eio_sid resolves to None).
		Re-check before any sio call that would raise; mutating a gone socket is a
		no-op. Safe against TOCTOU because the guarded call does not yield the hub."""
		return self._sio.manager.is_connected(self.sid, self.namespace)

	def join(self, room: str) -> None:
		if not self._connected():
			return
		self._sio.enter_room(self.sid, room, namespace=self.namespace)

	def leave(self, room: str) -> None:
		if not self._connected():
			return

		self._sio.leave_room(self.sid, room, namespace=self.namespace)

	def emit(self, event: str, data: object | None = None, room: str | None = None) -> None:
		"""Emit to a room, or to this client (default)."""
		self._sio.emit(event, data, to=room or self.sid, namespace=self.namespace)

	def get(self, key: str, default: object = None) -> object:
		"""Read transient per-socket state from the session."""
		return self._session.data.get(key, default)

	def set(self, key: str, value: object) -> None:
		"""Persist transient per-socket state onto the session."""
		self._session.data[key] = value
		if not self._connected():
			return
		self._sio.save_session(self.sid, self._session, namespace=self.namespace)

	def participants(self, room: str) -> list[str]:
		"""sids currently in ``room`` of this namespace."""
		sids = []
		for item in self._sio.manager.get_participants(self.namespace, room):
			sids.append(item[0] if isinstance(item, tuple) else item)
		return sids

	def user_of(self, sid: str) -> str | None:
		"""User on another socket's session, or None if it has none."""
		try:
			return self._sio.get_session(sid, namespace=self.namespace).user
		except KeyError:
			return None

	def has_permission(self, doctype: str, name: str | None = None) -> bool:
		"""HTTP permission check via the web process (no DB in realtime).

		For in-process checks use frappe.has_permission inside a
		frappe_context=True handler."""
		return self._session.has_permission(doctype, name)
