# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Standalone Python Socket.IO realtime server (asyncio + uvicorn).

Run with::

    python -m frappe.realtime.server

This process is fully separate from the web/gunicorn process. Calls back into the
web process (connect auth, permission checks) are async; blocking work (plain
handlers, frappe_context) is moved off the event loop into a worker thread.

To embed it instead, build a RealtimeServer and call run() on a thread you own::

    server = RealtimeServer()
    threading.Thread(target=server.run, daemon=True).start()
    ...
    server.stop()

Frappe itself never creates that thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import socketio
import uvicorn

from frappe.realtime.auth import close_clients
from frappe.realtime.bridge import RedisBridge
from frappe.realtime.config import RealtimeConfig, get_config
from frappe.realtime.dispatch import wire

logger = logging.getLogger("frappe.realtime")


class TolerantManager(socketio.AsyncManager):
	"""Re-ack a duplicate namespace connect instead of rejecting it.

	Default connect() returns None when the eio session is already on the namespace,
	which makes the server send CONNECT_ERROR ("Unable to connect") and poisons the
	live socket. Clients do reconnect redundantly (transport blips, StrictMode); the
	old Node server tolerated it. Reuse the existing sid so the connect is idempotent.
	"""

	async def connect(self, eio_sid: str, namespace: str) -> str | None:
		return await super().connect(eio_sid, namespace) or self.sid_from_eio_sid(eio_sid, namespace)


def create_sio() -> socketio.AsyncServer:
	"""Build the asgi-mode Socket.IO server.

	Origin / namespace / auth enforcement lives in auth.py; CORS is left open here
	so python-socketio does not pre-reject before that gate runs."""
	return socketio.AsyncServer(
		async_mode="asgi",
		cors_allowed_origins="*",
		cors_credentials=True,
		namespaces="*",
		client_manager=TolerantManager(),
		logger=logger,
		engineio_logger=logger,
	)


def load_handlers(sites_path: str | None = None) -> None:
	"""Import core handlers, then per-app handlers, so every @realtime.on
	registration runs before wire() binds events.

	None leaves the sites path to discover_app_handlers. Callers that know it, such
	as RealtimeServer, give the absolute path from the config: a relative one is read
	against the cwd, which serve() moves into sites/ and an embedder does not."""
	import frappe.realtime.handlers
	from frappe.realtime.registry import discover_app_handlers

	discover_app_handlers(sites_path=sites_path)


class RealtimeServer:
	"""Socket.IO realtime server on asyncio.

	Owns the Socket.IO server, the ASGI app, and the redis bridge. The bridge is
	started and stopped through the ASGI lifespan, so it always lives on the same
	loop uvicorn runs.
	"""

	def __init__(self, config: RealtimeConfig | None = None):
		self.config = config or get_config()
		self.sio = create_sio()
		self.bridge = RedisBridge(self.sio, self.config.redis_queue)
		# No other_asgi_app: engineio answers non-socket.io traffic with its own 404.
		self.app = socketio.ASGIApp(
			self.sio,
			on_startup=self._on_startup,
			on_shutdown=self._on_shutdown,
		)
		# wire() binds what is registered now, so handlers must be imported first.
		load_handlers(self.config.sites_path)
		wire(self.sio, self.config)
		self._server = uvicorn.Server(self._get_uvicorn_config())

	def run(self) -> None:
		"""Serve until stop(). Blocks, and works on any thread — uvicorn installs
		signal handlers only on the main thread."""
		if self.config.uds:
			# uvicorn binds without unlinking, so a leftover socket file would fail.
			if os.path.exists(self.config.uds):
				os.remove(self.config.uds)
			logger.info("Realtime service listening on UDS: %s", self.config.uds)
		else:
			logger.info("Realtime service listening on: ws://0.0.0.0:%s", self.config.port)

		self._server.run()

	def stop(self) -> None:
		"""Ask the server to shut down. run() returns once shutdown completes."""
		self._server.should_exit = True

	async def _on_startup(self) -> None:
		# Only when asked: this replaces the executor for the whole loop, and nothing
		# built in dispatches to a thread.
		if self.config.worker_threads:
			asyncio.get_running_loop().set_default_executor(
				ThreadPoolExecutor(
					max_workers=self.config.worker_threads, thread_name_prefix="realtime-worker"
				)
			)
		self.bridge.start()

	async def _on_shutdown(self) -> None:
		await self.bridge.stop()
		await close_clients()

	def _get_uvicorn_config(self) -> uvicorn.Config:
		"""Bind to the UDS path if configured, else to the port on all interfaces."""
		if self.config.uds:
			binding = {"uds": self.config.uds}
		else:
			binding = {"host": "0.0.0.0", "port": self.config.port}
		# log_config=None keeps the caller's logging setup; access logs would record
		# every polling request.
		return uvicorn.Config(self.app, log_config=None, access_log=False, **binding)


def serve(config: RealtimeConfig | None = None) -> None:
	config = config or get_config()

	if os.path.isdir("sites"):
		os.chdir("sites")

	RealtimeServer(config).run()


def main() -> None:
	logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
	serve()


if __name__ == "__main__":
	main()
