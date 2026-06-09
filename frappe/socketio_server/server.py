"""
PROTOTYPE: python-socketio replacement for apps/frappe/socketio.js

Run with:
    uvicorn frappe.socketio_server.server:asgi_app --host 0.0.0.0 --port 9000

Wire-compat with the existing socket.io-client browser library: the JS
frontend connects to `io(origin + "/" + site)` and that keeps working
because we accept any namespace dynamically (see DynamicServer below).
"""

import asyncio
import json

import redis.asyncio as aioredis
import socketio

from frappe.socketio_server import bench_conf
from frappe.socketio_server.auth import authenticate
from frappe.socketio_server.handlers import register_frappe_handlers


# --- Dynamic namespace support ----------------------------------------------
# python-socketio has no native equivalent of socket.io's `io.of(/regex/)`.
# We subclass AsyncServer to auto-register a namespace the first time a
# client tries to connect to it. Authentication still rejects unknown sites.
class DynamicServer(socketio.AsyncServer):
	async def _handle_connect(self, eio_sid, namespace, data):
		# python-socketio tracks function-style handlers in self.handlers and
		# class-style ones in self.namespace_handlers. Check both.
		known = namespace in self.handlers or namespace in self.namespace_handlers
		if not known and namespace != "/":
			register_frappe_handlers(self, namespace)
		return await super()._handle_connect(eio_sid, namespace, data)


# --- Server setup -----------------------------------------------------------
conf = bench_conf()
redis_url = conf.get("redis_queue") or "redis://127.0.0.1:11311"

sio = DynamicServer(
	async_mode="asgi",
	cors_allowed_origins="*",  # mirrored to request origin by CORSReflectMiddleware below
	cors_credentials=True,
	client_manager=socketio.AsyncRedisManager(redis_url),
)


@sio.event
async def connect(sid, environ, auth):
	"""Default-namespace connect — used only for health checks; real
	traffic lands on per-site namespaces handled by register_frappe_handlers."""
	return True


# Register an on_connect for *every* dynamically-attached namespace.
# This is what DynamicServer wires up on first connect to a site.
async def on_site_connect(sid, environ, auth, namespace):
	ok, ctx = await authenticate(environ, namespace)
	if not ok:
		raise socketio.exceptions.ConnectionRefusedError(ctx)  # ctx is err msg

	await sio.save_session(sid, ctx, namespace=namespace)
	# Per-app handler discovery via hooks instead of filesystem walk.
	# Each app declares `realtime_handlers = "myapp.realtime.handlers.setup"`
	# in its hooks.py; we call them with (sio, sid, namespace, session).
	# Per-app handler discovery via hooks (frappe.get_hooks) — disabled
	# in this prototype because it requires a full frappe.init() per
	# connect. The base frappe handlers in handlers.py cover the common
	# rooms. Real impl: cache hook lookups at server startup keyed by site.


# --- Redis pub/sub fan-out --------------------------------------------------
async def consume_events():
	"""Bridge Python publishers (frappe.realtime.emit_via_redis) into socket.io."""
	r = aioredis.from_url(redis_url, decode_responses=True)
	pubsub = r.pubsub()
	await pubsub.subscribe("events")
	async for msg in pubsub.listen():
		if msg["type"] != "message":
			continue
		try:
			payload = json.loads(msg["data"])
		except json.JSONDecodeError:
			continue
		namespace = "/" + payload["namespace"]
		if payload.get("room"):
			await sio.emit(
				payload["event"],
				payload["message"],
				room=payload["room"],
				namespace=namespace,
			)
		else:
			# Site-less broadcast (e.g. esbuild "build" event).
			await sio.emit(payload["event"], payload["message"])


# --- ASGI entrypoint --------------------------------------------------------
class CORSReflectMiddleware:
	"""Reflect the request Origin header into Access-Control-Allow-Origin,
	matching the Node socket.io `cors: { origin: true, credentials: true }`
	behaviour. Required because browsers reject `*` with credentials."""

	def __init__(self, app):
		self.app = app

	async def __call__(self, scope, receive, send):
		if scope["type"] not in ("http", "websocket"):
			return await self.app(scope, receive, send)

		origin = b""
		for k, v in scope.get("headers", []):
			if k == b"origin":
				origin = v
				break

		async def send_wrapper(message):
			if message["type"] == "http.response.start" and origin:
				headers = [
					(k, v)
					for k, v in message.get("headers", [])
					if k.lower() not in (b"access-control-allow-origin", b"access-control-allow-credentials")
				]
				headers.append((b"access-control-allow-origin", origin))
				headers.append((b"access-control-allow-credentials", b"true"))
				message["headers"] = headers
			await send(message)

		await self.app(scope, receive, send_wrapper)


asgi_app = CORSReflectMiddleware(
	socketio.ASGIApp(sio, on_startup=lambda: asyncio.create_task(consume_events()))
)
