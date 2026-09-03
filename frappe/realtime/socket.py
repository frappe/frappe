# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from frappe.realtime.auth import Session

if TYPE_CHECKING:
	from socketio import AsyncServer

# Seconds. A backstop against a wedged worker thread, not a latency budget.
LOOP_CALL_TIMEOUT = 120


class Socket:
	"""Typed Socket wrapper passed to handlers.

	Thin facade over the python-socketio server bound to one sid + namespace,
	plus the authenticated Session stored at connect. Read-only identity fields
	and emit/room helpers; identity + has_permission delegate to the Session, so
	the wrapper carries no auth/HTTP logic itself.

	The methods are coroutines because the underlying AsyncServer calls are.
	Handlers written as plain functions get SyncSocket instead.
	"""

	def __init__(self, sio: AsyncServer, sid: str, namespace: str, session: Session):
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

		A handler yields the loop at every await (e.g. has_permission does an HTTP
		round-trip to the web process). The client may disconnect in that window, after
		which the namespace is gone from the manager — enter_room then raises "sid is
		not connected to requested namespace" and save_session raises KeyError
		(eio_sid resolves to None). Re-check before any sio call that would raise;
		mutating a gone socket is a no-op. Safe against TOCTOU because the guarded
		call does not yield the loop before it reads the manager."""
		return self._sio.manager.is_connected(self.sid, self.namespace)

	async def join(self, room: str) -> None:
		if not self._connected():
			return
		await self._sio.enter_room(self.sid, room, namespace=self.namespace)

	async def leave(self, room: str) -> None:
		if not self._connected():
			return

		await self._sio.leave_room(self.sid, room, namespace=self.namespace)

	async def emit(self, event: str, data: object | None = None, room: str | None = None) -> None:
		"""Emit to a room, or to this client (default)."""
		await self._sio.emit(event, data, to=room or self.sid, namespace=self.namespace)

	def get(self, key: str, default: object = None) -> object:
		"""Read transient per-socket state from the session."""
		return self._session.data.get(key, default)

	async def set(self, key: str, value: object) -> None:
		"""Persist transient per-socket state onto the session."""
		self._session.data[key] = value
		if not self._connected():
			return
		await self._sio.save_session(self.sid, self._session, namespace=self.namespace)

	def participants(self, room: str) -> list[str]:
		"""sids currently in ``room`` of this namespace."""
		sids = []
		for item in self._sio.manager.get_participants(self.namespace, room):
			sids.append(item[0] if isinstance(item, tuple) else item)
		return sids

	async def user_of(self, sid: str) -> str | None:
		"""User on another socket's session, or None if it has none."""
		try:
			return (await self._sio.get_session(sid, namespace=self.namespace)).user
		except KeyError:
			return None

	async def has_permission(self, doctype: str, name: str | None = None) -> bool:
		"""HTTP permission check via the web process (no DB in realtime).

		Async, so it holds no worker thread. For in-process checks use
		frappe.has_permission inside a frappe_context=True handler."""
		return await self._session.has_permission(doctype, name)


class SyncSocket:
	"""Blocking Socket facade for handlers that run in a worker thread.

	Same API as Socket, minus the awaits: each coroutine is submitted back to the
	server's event loop and waited on from this thread. Handed to plain (non-async)
	handlers and to every frappe_context handler.
	"""

	def __init__(self, socket: Socket, loop: asyncio.AbstractEventLoop):
		self._socket = socket
		self._loop = loop

	@property
	def sid(self) -> str:
		return self._socket.sid

	@property
	def namespace(self) -> str:
		return self._socket.namespace

	@property
	def site(self) -> str:
		return self._socket.site

	@property
	def user(self) -> str:
		return self._socket.user

	@property
	def user_type(self) -> str:
		return self._socket.user_type

	@property
	def installed_apps(self) -> list[str]:
		return self._socket.installed_apps

	def join(self, room: str) -> None:
		self._run(self._socket.join(room))

	def leave(self, room: str) -> None:
		self._run(self._socket.leave(room))

	def emit(self, event: str, data: object | None = None, room: str | None = None) -> None:
		self._run(self._socket.emit(event, data, room))

	def get(self, key: str, default: object = None) -> object:
		return self._socket.get(key, default)

	def set(self, key: str, value: object) -> None:
		self._run(self._socket.set(key, value))

	def participants(self, room: str) -> list[str]:
		return self._socket.participants(room)

	def user_of(self, sid: str) -> str | None:
		return self._run(self._socket.user_of(sid))

	def has_permission(self, doctype: str, name: str | None = None) -> bool:
		return self._run(self._socket.has_permission(doctype, name))

	def _run(self, coro):
		"""Submit a coroutine to the server loop and block this thread on it.

		Bounded: a loop that stops mid-handler would never resolve the future,
		wedging the thread and the executor join that process exit waits on."""
		if self._loop.is_closed():
			coro.close()
			raise RuntimeError("realtime event loop is closed")

		future = asyncio.run_coroutine_threadsafe(coro, self._loop)
		try:
			return future.result(LOOP_CALL_TIMEOUT)
		except TimeoutError:
			future.cancel()
			raise
