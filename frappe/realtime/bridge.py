# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import redis.asyncio
from redis.exceptions import RedisError

if TYPE_CHECKING:
	from socketio import AsyncServer

logger = logging.getLogger("frappe.realtime")

EVENTS_CHANNEL = "events"
RECONNECT_DELAY = 1.0  # seconds between redis reconnect attempts


@dataclass(slots=True)
class RealtimeEvent:
	"""Parsed ``events`` channel message"""

	event: str
	message: Any = None
	room: str | None = None
	namespace: str | None = None

	@classmethod
	def from_raw(cls, raw: str | bytes | bytearray | None) -> RealtimeEvent:
		data = json.loads(raw)
		return cls(
			event=data["event"],
			message=data.get("message"),
			room=data.get("room"),
			namespace=data.get("namespace"),
		)


class RedisBridge:
	"""Redis -> Socket.IO bridge.

	Subscribes to the queue redis ``events`` channel — the same channel
	frappe.realtime.emit_via_redis publishes to — and re-emits each message to the
	connected sockets. The message shape is the frozen external contract:

	    {"namespace": "site", "room": "room", "event": "event", "message": {}}

	- with ``room``: emit to that room in namespace ``/{namespace}``
	- without ``room``: broadcast to every connected site namespace (build events)

	Runs as its own asyncio task; reconnects on redis failure and skips malformed
	messages without crashing.
	"""

	def __init__(self, sio: AsyncServer, redis_url: str):
		self.sio: AsyncServer = sio
		self.redis_url = redis_url
		self._task: asyncio.Task | None = None

	def start(self) -> asyncio.Task:
		"""Spawn the subscriber task on the running loop. Returns the task."""
		self._task = asyncio.create_task(self._run())
		return self._task

	async def stop(self) -> None:
		if not self._task:
			return
		self._task.cancel()
		with suppress(asyncio.CancelledError):
			await self._task
		self._task = None

	async def _run(self) -> None:
		while True:
			try:
				await self._listen()
			except asyncio.CancelledError:
				raise
			except RedisError as e:
				logger.warning("Redis bridge connection lost (%s); reconnecting in %ss", e, RECONNECT_DELAY)
			except Exception:
				logger.exception("Redis bridge crashed; reconnecting in %ss", RECONNECT_DELAY)
			await asyncio.sleep(RECONNECT_DELAY)

	async def _listen(self) -> None:
		"""Subscribe and pump messages until the connection drops."""
		client = redis.asyncio.from_url(self.redis_url)
		try:
			pubsub = client.pubsub(ignore_subscribe_messages=True)
			await pubsub.subscribe(EVENTS_CHANNEL)
			logger.info("Redis bridge subscribed to %r on %s", EVENTS_CHANNEL, self.redis_url)
			async for message in pubsub.listen():
				if message.get("type") == "message":
					await self._handle(message.get("data"))
		finally:
			with suppress(Exception):
				await client.aclose()

	async def _handle(self, raw: str | bytes | bytearray | None) -> None:
		try:
			evt = RealtimeEvent.from_raw(raw)
		except (ValueError, TypeError, KeyError) as e:
			logger.warning("Redis bridge skipping malformed message (%s): %r", e, raw)
			return

		if evt.room:
			if not evt.namespace:
				logger.warning("Redis bridge skipping room message with no namespace: %r", raw)
				return
			await self.sio.emit(evt.event, evt.message, room=evt.room, namespace="/" + evt.namespace)
		else:
			# No room -> broadcast to every connected site namespace (build events).
			for ns in list(self.sio.manager.rooms.keys()):
				await self.sio.emit(evt.event, evt.message, namespace=ns)
