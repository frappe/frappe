# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from frappe.realtime import flow_handlers
from frappe.tests import UnitTestCase


class FakePubSub:
	def __init__(self):
		self.messages: asyncio.Queue = asyncio.Queue()
		self.channels: set[str] = set()
		self.fail_next = False

	async def subscribe(self, *channels):
		if self.fail_next:
			self.fail_next = False
			raise ConnectionError("redis is down")
		for channel in channels:
			self.channels.add(channel)
			await self.messages.put({"type": "subscribe", "channel": channel})

	async def unsubscribe(self, *channels):
		self.channels.difference_update(channels)

	async def get_message(self, timeout=1.0):
		try:
			return await asyncio.wait_for(self.messages.get(), timeout)
		except TimeoutError:
			return None


class FakeSocket:
	site, sid, user = "s1", "sid1", "a@example.com"

	def __init__(self, allowed: bool):
		self.allowed = allowed
		self.rooms: set[str] = set()
		self.emits: list[tuple] = []
		self.data: dict = {}

	async def has_permission(self, doctype, name):
		return self.allowed

	async def join(self, room):
		self.rooms.add(room)

	async def leave(self, room):
		self.rooms.discard(room)

	def participants(self, room):
		return [self.sid] if room in self.rooms else []

	async def emit(self, event, data=None, room=None):
		self.emits.append((event, data, room))

	def get(self, key, default=None):
		return self.data.get(key, default)

	async def set(self, key, value):
		self.data[key] = value


class TestRealtimeRelay(UnitTestCase):
	def test_relays_session_events_only_to_a_socket_that_may_read_them(self):
		async def run():
			pubsub = FakePubSub()
			relay = flow_handlers.Relay()
			self.assertFalse(await relay.subscribe(FakeSocket(allowed=False), "session-1"))
			self.assertEqual(relay.subscriptions, {})

			socket = FakeSocket(allowed=True)
			with patch.object(flow_handlers, "redis_client", lambda: SimpleNamespace(pubsub=lambda: pubsub)):
				self.assertTrue(await relay.subscribe(socket, "session-1"))

			channel = "harness:s1:session-1"
			await pubsub.messages.put({"type": "message", "channel": channel, "data": json.dumps({"seq": 1})})
			await asyncio.sleep(0.1)
			relay.listener.cancel()
			self.assertIn(("flow:event", {"seq": 1}, channel), socket.emits)

		asyncio.run(run())

	def test_a_failed_subscribe_forgets_its_channels_so_a_retry_listens_again(self):
		async def run():
			pubsub = FakePubSub()
			relay = flow_handlers.Relay()
			socket = FakeSocket(allowed=True)
			subscribe = pubsub.subscribe

			async def disconnect_then_fail(*channels):
				pubsub.subscribe = subscribe
				await relay.release(socket, "session-1")
				raise ConnectionError("redis is down")

			with patch.object(flow_handlers, "redis_client", lambda: SimpleNamespace(pubsub=lambda: pubsub)):
				pubsub.fail_next = True
				with self.assertRaises(ConnectionError):
					await relay.subscribe(socket, "session-1")
				# a disconnect while the retry is in flight leaves no channel behind either
				pubsub.subscribe = disconnect_then_fail
				with self.assertRaises(ConnectionError):
					await relay.subscribe(socket, "session-1")
				self.assertEqual(relay.channel_ready, {})

				self.assertTrue(await relay.subscribe(FakeSocket(allowed=True), "session-2"))
			relay.listener.cancel()
			self.assertIn("flow-access:s1", pubsub.channels)

		asyncio.run(run())
