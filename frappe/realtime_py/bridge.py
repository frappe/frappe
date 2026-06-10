# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Redis -> Socket.IO bridge.

Subscribes to the no-auth queue redis ``events`` channel — the same channel
frappe.realtime.emit_via_redis publishes to — and re-emits each message to the
connected sockets. The message shape is the frozen external contract::

    {"namespace": "site", "room": "room", "event": "event", "message": {}}

- with ``room``: emit to that room in namespace ``/{namespace}``
- without ``room``: broadcast to every connected site namespace (build events)

Runs in its own greenlet; reconnects on redis failure and skips malformed
messages without crashing.
"""

import json
import logging

import gevent
import redis

logger = logging.getLogger("frappe.realtime")

EVENTS_CHANNEL = "events"
RECONNECT_DELAY = 1.0  # seconds between redis reconnect attempts


class RedisBridge:
	def __init__(self, sio, redis_url: str):
		self.sio = sio
		self.redis_url = redis_url
		self._greenlet = None

	def start(self):
		"""Spawn the subscriber greenlet. Returns the greenlet."""
		self._greenlet = gevent.spawn(self._run)
		return self._greenlet

	def _run(self):
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

	def _handle(self, raw):
		try:
			data = json.loads(raw)
			namespace = "/" + data["namespace"]
			event = data["event"]
			message = data.get("message")
			room = data.get("room")
		except (ValueError, TypeError, KeyError) as e:
			logger.warning("Redis bridge skipping malformed message (%s): %r", e, raw)
			return

		if room:
			self.sio.emit(event, message, room=room, namespace=namespace)
		else:
			# No room -> broadcast to every connected site namespace (build events).
			for ns in list(self.sio.manager.rooms.keys()):
				self.sio.emit(event, message, namespace=ns)


def start_bridge(sio, redis_url: str) -> RedisBridge:
	bridge = RedisBridge(sio, redis_url)
	bridge.start()
	return bridge
