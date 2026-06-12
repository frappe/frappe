# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Standalone Python Socket.IO realtime server (gevent).

Run with::

    python -m frappe.realtime.server

This process is fully separate from the web/gunicorn process. It runs on gevent
and forces the pure-python PyMySQL driver — the mysqlclient C extension has a
blocking socket that cannot be monkeypatched and would stall the gevent hub.

HARD REQUIREMENT: gevent.monkey.patch_all() must run before anything imports
frappe / redis / pymysql / socketio. It is therefore the very first statement in
this module, ahead of every other import.
"""

# ---------------------------------------------------------------------------
# MUST BE FIRST. Do not move imports above this block.
from gevent import monkey

monkey.patch_all()
# ---------------------------------------------------------------------------

import logging
import sys

import socketio
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

from frappe.realtime.bridge import start_bridge
from frappe.realtime.config import RealtimeConfig, get_config
from frappe.realtime.dispatch import wire

logger = logging.getLogger("frappe.realtime")


def assert_no_mysqlclient() -> None:
	"""Fail loudly if the mysqlclient C extension was imported.

	Its blocking socket cannot be monkeypatched and will stall the gevent hub.
	The realtime process must use PyMySQL only (see force_pymysql)."""
	if "MySQLdb" in sys.modules:
		raise RuntimeError(
			"mysqlclient (MySQLdb) is imported in the realtime process. "
			"It is a C extension whose blocking socket stalls the gevent hub. "
			"The realtime process must use PyMySQL only."
		)


def force_pymysql(conf) -> None:
	"""Force the pure-python PyMySQL driver on a site conf.

	frappe.database.get_db selects mysqlclient when conf.use_mysqlclient is truthy
	(the default). Flip it off so any DB connection opened inside a handler context
	uses the gevent-patchable PyMySQL path instead. Called by context.py per context."""
	conf["use_mysqlclient"] = 0


def health_app(environ, start_response):
	"""Minimal WSGI app for non-socket.io routes. Serves GET /health."""
	if environ.get("PATH_INFO") == "/health":
		start_response("200 OK", [("Content-Type", "text/plain")])
		return [b"ok"]
	start_response("404 Not Found", [("Content-Type", "text/plain")])
	return [b"not found"]


class TolerantManager(socketio.manager.Manager):
	"""Re-ack a duplicate namespace connect instead of rejecting it.

	Default connect() returns None when the eio session is already on the namespace,
	which makes the server send CONNECT_ERROR ("Unable to connect") and poisons the
	live socket. Clients do reconnect redundantly (transport blips, StrictMode); the
	old Node server tolerated it. Reuse the existing sid so the connect is idempotent.
	"""

	def connect(self, eio_sid: str, namespace: str) -> str | None:
		return super().connect(eio_sid, namespace) or self.sid_from_eio_sid(eio_sid, namespace)


def create_sio() -> socketio.Server:
	"""Build the gevent-mode Socket.IO server.

	Origin / namespace / auth enforcement lives in auth.py (task 6); CORS is left
	open here so python-socketio does not pre-reject before that gate runs."""
	return socketio.Server(
		async_mode="gevent",
		cors_allowed_origins="*",
		cors_credentials=True,
		namespaces="*",
		client_manager=TolerantManager(),
		logger=logger,
		engineio_logger=logger,
	)


def create_app(sio: socketio.Server) -> socketio.WSGIApp:
	"""Wrap the Socket.IO server in a WSGI app, with /health alongside."""
	return socketio.WSGIApp(sio, wsgi_app=health_app)


# Module-level server instance other modules (bridge, auth, handlers) attach to.
sio = create_sio()
app = create_app(sio)


def _make_listener(config: RealtimeConfig):
	"""Build the WSGIServer listener: a bound AF_UNIX socket for UDS, else (host, port)."""
	if config.uds:
		import os
		import socket as _socket

		if os.path.exists(config.uds):
			os.remove(config.uds)
		sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
		sock.bind(config.uds)
		sock.listen(256)
		return sock
	return ("0.0.0.0", config.port)


def serve(config: RealtimeConfig | None = None) -> None:
	import os

	assert_no_mysqlclient()
	config = config or get_config()

	if os.path.isdir("sites"):
		os.chdir("sites")

	# Import core handlers, then discover per-app handlers, so every @realtime.on
	# registration runs before wire() binds events.
	import frappe.realtime.handlers
	from frappe.realtime.registry import discover_app_handlers

	discover_app_handlers(sites_path=".")

	wire(sio, config)

	start_bridge(sio, config.redis_queue)

	listener = _make_listener(config)
	server = WSGIServer(listener, app, handler_class=WebSocketHandler, log=logger, error_log=logger)

	if config.uds:
		logger.info("Realtime service listening on UDS: %s", config.uds)
	else:
		logger.info("Realtime service listening on: ws://0.0.0.0:%s", config.port)

	server.serve_forever()


def main() -> None:
	logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
	serve()


if __name__ == "__main__":
	main()
