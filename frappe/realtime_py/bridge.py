# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

import gevent
import redis

if TYPE_CHECKING:
	from gevent.greenlet import Greenlet
	from socketio.server import Server as SocketIOServer

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

	Runs in its own greenlet; reconnects on redis failure and skips malformed
	messages without crashing.
	"""

	def __init__(self, sio: SocketIOServer, redis_url: str):
		self.sio: SocketIOServer = sio
		self.redis_url = redis_url
		self._greenlet: Greenlet | None = None

	def start(self) -> Greenlet:
		"""Spawn the subscriber greenlet. Returns the greenlet."""
		self._greenlet = gevent.spawn(self._run)
		return self._greenlet

	def _run(self) -> NoReturn:
		while True:
			try:
				client = redis.from_url(self.redis_url)
				pubsub = client.pubsub(ignore_subscribe_messages=True)
				pubsub.subscribe(EVENTS_CHANNEL)
				logger.info("Redis bridge subscribed to %r on %s", EVENTS_CHANNEL, self.redis_url)
				for message in pubsub.listen():
					if message.get("type") != "message":
						continue
					self._handle(message.get("data"))
			except redis.exceptions.RedisError as e:
				logger.warning("Redis bridge connection lost (%s); reconnecting in %ss", e, RECONNECT_DELAY)
				gevent.sleep(RECONNECT_DELAY)
			except Exception:
				logger.exception("Redis bridge crashed; reconnecting in %ss", RECONNECT_DELAY)
				gevent.sleep(RECONNECT_DELAY)

	def _handle(self, raw: str | bytes | bytearray | None) -> None:
		try:
			evt = RealtimeEvent.from_raw(raw)
		except (ValueError, TypeError, KeyError) as e:
			logger.warning("Redis bridge skipping malformed message (%s): %r", e, raw)
			return

		if evt.room:
			if not evt.namespace:
				logger.warning("Redis bridge skipping room message with no namespace: %r", raw)
				return
			self.sio.emit(evt.event, evt.message, room=evt.room, namespace="/" + evt.namespace)
		else:
			# No room -> broadcast to every connected site namespace (build events).
			for ns in list(self.sio.manager.rooms.keys()):
				self.sio.emit(evt.event, evt.message, namespace=ns)


def start_bridge(sio: SocketIOServer, redis_url: str) -> RedisBridge:
	bridge = RedisBridge(sio, redis_url)
	bridge.start()
	return bridge
