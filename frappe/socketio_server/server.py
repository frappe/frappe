"""python-socketio replacement for apps/frappe/socketio.js.

Run with: python -m frappe.socketio_server
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
import socketio

from frappe.socketio_server import redis_url
from frappe.socketio_server.handlers import register_frappe_handlers

logger = logging.getLogger("frappe.socketio")


class DynamicServer(socketio.AsyncServer):
	"""python-socketio has no equivalent of socket.io's `io.of(/regex/)`
	namespaces, so register handlers on first connect to a namespace.
	authenticate() still rejects namespaces that don't match a valid site."""

	async def _handle_connect(self, eio_sid, namespace, data):
		known = namespace in self.handlers or namespace in self.namespace_handlers
		if not known and namespace != "/":
			register_frappe_handlers(self, namespace)
		return await super()._handle_connect(eio_sid, namespace, data)

	def site_namespaces(self) -> set[str]:
		return (set(self.handlers) | set(self.namespace_handlers)) - {"/"}


sio = DynamicServer(
	async_mode="asgi",
	cors_allowed_origins="*",  # mirrored to request origin by CORSReflectMiddleware below
	cors_credentials=True,
	client_manager=socketio.AsyncRedisManager(redis_url()),
)


@sio.event
async def connect(sid, environ, auth=None):
	"""Default-namespace connect — only used for health checks."""
	return True


# --- Redis pub/sub fan-out ---------------------------------------------------
async def consume_events():
	"""Bridge frappe.realtime.emit_via_redis publishes into socket.io.
	Reconnects with backoff if redis drops."""
	delay = 1
	while True:
		try:
			client = aioredis.from_url(redis_url(), decode_responses=True)
			pubsub = client.pubsub()
			await pubsub.subscribe("events")
			delay = 1
			async for msg in pubsub.listen():
				if msg["type"] != "message":
					continue
				try:
					payload = json.loads(msg["data"])
					await _dispatch(payload)
				except Exception:
					logger.warning("failed to dispatch realtime event: %r", msg["data"], exc_info=True)
		except (aioredis.RedisError, OSError):
			logger.warning("events subscriber lost redis, retrying in %ss", delay, exc_info=True)
			await asyncio.sleep(delay)
			delay = min(delay * 2, 30)


async def _dispatch(payload: dict):
	event, message = payload["event"], payload.get("message")
	if payload.get("room"):
		await sio.emit(event, message, room=payload["room"], namespace="/" + payload["namespace"])
	else:
		# site-less broadcast (e.g. esbuild build event) goes to every namespace
		for namespace in sio.site_namespaces():
			await sio.emit(event, message, namespace=namespace)


# --- ASGI entrypoint ----------------------------------------------------------
class CORSReflectMiddleware:
	"""Reflect the request Origin into Access-Control-Allow-Origin —
	browsers reject `*` with credentials."""

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


_consumer_task = None


async def _start_event_consumer():
	global _consumer_task
	_consumer_task = asyncio.create_task(consume_events())


asgi_app = CORSReflectMiddleware(socketio.ASGIApp(sio, on_startup=_start_event_consumer))
