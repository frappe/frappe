# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Wire the registry into the Socket.IO server.

wire() binds the lifecycle events and one dispatcher per registered event, all on
the catch-all namespace ("*") so every per-site namespace /{site} is served by the
same handlers. Per event, dispatch:

- loads the session stored at connect and builds a typed Socket
- install-scoping: runs a handler only if its app is on the site's installed_apps
- guest gate: skips a handler when user == "Guest" and the handler is not allow_guest
- context wrap: opens frappe_context for handlers registered with frappe_context=True

Handler errors are logged and swallowed so one bad handler never drops the socket.
Concrete events are bound (rather than a combined catch-all) to avoid ambiguity in
python-socketio's argument order; the namespace is always prepended for namespace="*".
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from frappe.realtime.auth import authenticate
from frappe.realtime.config import RealtimeConfig
from frappe.realtime.context import frappe_context
from frappe.realtime.registry import realtime
from frappe.realtime.socket import Socket

if TYPE_CHECKING:
	from socketio.server import Server as SocketIOServer

logger = logging.getLogger("frappe.realtime")

RESERVED_EVENTS = ("connect", "disconnect")


def _run_handlers(
	sio: SocketIOServer,
	event: str,
	namespace: str,
	sid: str,
	args: tuple[object, ...],
) -> None:
	handlers = realtime.handlers_for(event)
	if not handlers:
		return

	try:
		session = sio.get_session(sid, namespace=namespace)
	except KeyError:
		return

	socket = Socket(sio, sid, namespace, session)

	for handler in handlers:
		if handler.app not in socket.installed_apps:
			continue
		if socket.user == "Guest" and not handler.allow_guest:
			continue
		try:
			if handler.frappe_context:
				with frappe_context(socket.site, socket.user):
					handler.fn(socket, *args)
			else:
				handler.fn(socket, *args)
		except Exception:
			logger.exception("handler error: event=%s app=%s", event, handler.app)


def _make_dispatcher(sio: SocketIOServer, event: str) -> Callable[..., None]:
	def dispatcher(namespace: str, sid: str, *args: object) -> None:
		_run_handlers(sio, event, namespace, sid, args)

	return dispatcher


def wire(sio: SocketIOServer, config: RealtimeConfig) -> None:
	"""Bind connect / disconnect and every registered event onto namespace '*'."""

	def connect(namespace: str, sid: str, environ: dict, auth: object | None = None) -> None:
		session = authenticate(environ, namespace, config)
		sio.save_session(sid, session, namespace=namespace)
		_run_handlers(sio, "connect", namespace, sid, ())

	def disconnect(namespace: str, sid: str, reason: object | None = None) -> None:
		# socketio 5.11+ passes a disconnect reason; accept and ignore it so the
		# handler binds directly instead of relying on the library's TypeError retry.
		_run_handlers(sio, "disconnect", namespace, sid, ())

	sio.on("connect", connect, namespace="*")
	sio.on("disconnect", disconnect, namespace="*")

	for event in list(realtime.events()):
		if event in RESERVED_EVENTS:
			continue
		sio.on(event, _make_dispatcher(sio, event), namespace="*")
		logger.debug("wired event %r (%d handler(s))", event, len(realtime.handlers_for(event)))
