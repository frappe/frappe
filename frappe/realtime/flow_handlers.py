# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

# Relays flow server events (Redis channel `harness:<site>:<session>`) to subscribed
# browsers from Frappe's Python realtime server. The Node server loads realtime/flow_handlers.js.

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

import redis.asyncio
from redis.exceptions import RedisError

import frappe
from frappe.realtime import Socket, realtime
from frappe.realtime.config import get_config

logger = logging.getLogger("frappe.flow.realtime")

EVENT = "flow:event"
RESYNC = "flow:resync"
RESUBSCRIBE = "flow:resubscribe"
SESSION_CHANNEL = "harness:"
RESYNC_ALL = "harness-resync:all"
RESYNC_SITE = "harness-resync:site:"
ACCESS_SITE = "flow-access:"
SESSION_NAME = re.compile(r"[\w.-]{1,140}", re.ASCII)
SUBSCRIBE_TIMEOUT = 10
RECONNECT_DELAY = 1


@dataclass
class Subscription:
	site: str
	session: str
	# Any subscriber's socket emits to the room; the room outlives the socket that opened it.
	emitter: Socket
	sockets: dict[str, Socket] = field(default_factory=dict)
	ready: asyncio.Future | None = None


class Relay:
	"""One Redis subscriber for the process, shared by every subscribed socket."""

	def __init__(self) -> None:
		self.subscriptions: dict[str, Subscription] = {}
		# channel -> resolved once Redis confirms its subscription
		self.channel_ready: dict[str, asyncio.Future] = {}
		self.pubsub = None
		self.listener: asyncio.Task | None = None

	async def subscribe(self, socket: Socket, session: object) -> bool:
		"""Join the session's room once the caller may read it and the Redis channel is live."""
		if not is_valid_name(session) or not await socket.has_permission("Flow Session", session):
			return False

		channel = f"{SESSION_CHANNEL}{socket.site}:{session}"
		await socket.join(channel)
		# a socket that left during the permission check is not in the room
		if socket.sid not in socket.participants(channel):
			return False

		entry = self.subscriptions.get(channel)
		if entry is None:
			entry = Subscription(socket.site, session, socket)
			entry.ready = asyncio.ensure_future(self.listen(channel, socket.site))
			self.subscriptions[channel] = entry
		entry.sockets[socket.sid] = socket
		sessions = socket.get("flow_sessions", [])
		if session not in sessions:
			await socket.set("flow_sessions", [*sessions, session])

		try:
			await asyncio.shield(entry.ready)
		except Exception:
			if self.subscriptions.get(channel) is entry:
				del self.subscriptions[channel]
			await self.release(socket, session)
			raise
		return True

	async def release(self, socket: Socket, session: str) -> None:
		sessions = socket.get("flow_sessions", [])
		if session not in sessions:
			return
		await socket.set("flow_sessions", [name for name in sessions if name != session])

		channel = f"{SESSION_CHANNEL}{socket.site}:{session}"
		await socket.leave(channel)
		entry = self.subscriptions.get(channel)
		if entry is None:
			return
		entry.sockets.pop(socket.sid, None)
		if entry.sockets:
			return

		del self.subscriptions[channel]
		self.channel_ready.pop(channel, None)
		try:
			await self.pubsub.unsubscribe(channel)
		except RedisError:
			pass

	async def listen(self, channel: str, site: str) -> None:
		"""Subscribe the session channel, and the site's resync and access channels on first use."""
		channels = [channel, RESYNC_ALL, RESYNC_SITE + site, ACCESS_SITE + site]
		loop = asyncio.get_running_loop()
		created = {name: loop.create_future() for name in channels if name not in self.channel_ready}
		self.channel_ready.update(created)
		waits = [asyncio.shield(self.channel_ready[name]) for name in channels]

		try:
			if self.pubsub is None:
				self.pubsub = redis_client().pubsub()
			await self.pubsub.subscribe(*created)
			if self.listener is None:
				self.listener = asyncio.create_task(self.run())
			# The ack must not beat the Redis subscriptions, or a run started on it loses events
			# or the access changes that stop a stream.
			await asyncio.wait_for(asyncio.gather(*waits), SUBSCRIBE_TIMEOUT)
		except Exception as error:
			# A retry subscribes these again, and a listen waiting on them fails with this one.
			# A disconnect may have released the session channel already.
			for name, ready in created.items():
				if self.channel_ready.get(name) is ready:
					del self.channel_ready[name]
				if not ready.done():
					ready.set_exception(error)
					ready.exception()  # retrieved, so one no other listen awaits logs nothing
			raise

	async def run(self) -> None:
		"""Read Redis until the process stops. redis-py reconnects and subscribes again by itself."""
		lost_connection = False
		while True:
			try:
				message = await self.pubsub.get_message(timeout=1.0)
			except asyncio.CancelledError:
				raise
			except (RedisError, OSError) as error:
				logger.warning("flow: redis error (%s); reconnecting", error)
				lost_connection = True
				await asyncio.sleep(RECONNECT_DELAY)
				continue

			# Pub/sub cannot replay events missed while the connection was down.
			if lost_connection:
				lost_connection = False
				await self.resync(RESYNC_ALL, "{}")
			if message:
				await self.handle(message)

	async def handle(self, message: dict) -> None:
		channel = message["channel"]
		if message["type"] == "subscribe":
			ready = self.channel_ready.get(channel)
			if ready and not ready.done():
				ready.set_result(True)
			return
		if message["type"] != "message":
			return

		try:
			if channel.startswith(SESSION_CHANNEL):
				await self.deliver(channel, message["data"])
			elif channel.startswith(ACCESS_SITE):
				await self.recheck(channel, message["data"])
			else:
				await self.resync(channel, message["data"])
		except Exception:
			logger.exception("flow: relay failed for %s", channel)

	async def deliver(self, channel: str, data: str) -> None:
		entry = self.subscriptions.get(channel)
		event = parse(data)
		if entry and event:
			await entry.emitter.emit(EVENT, event, room=channel)

	async def resync(self, channel: str, data: str) -> None:
		"""The daemon asks for a resync when it had to drop events, naming the sessions if it can."""
		notice = parse(data)
		if notice is None:
			return
		site = None if channel == RESYNC_ALL else channel.removeprefix(RESYNC_SITE)
		named = set(notice["session_ids"]) if isinstance(notice.get("session_ids"), list) else None
		for room, entry in list(self.subscriptions.items()):
			if (site and entry.site != site) or (named is not None and entry.session not in named):
				continue
			await entry.emitter.emit(RESYNC, {"session": entry.session}, room=room)

	async def recheck(self, channel: str, data: str) -> None:
		"""The site names who lost a view (no one, for an everyone share) and the session's owner.
		Anyone else stays only if the site says yes; one who leaves is told to subscribe again."""
		notice = parse(data)
		if notice is None or not is_valid_name(notice.get("session")):
			return
		site = channel.removeprefix(ACCESS_SITE)
		for entry in list(self.subscriptions.values()):
			if entry.site != site or entry.session != notice["session"]:
				continue
			for socket in list(entry.sockets.values()):
				if socket.user == notice.get("owner"):
					continue
				if notice.get("user") and socket.user != notice["user"]:
					continue
				if await socket.has_permission("Flow Session", entry.session):
					continue
				await self.release(socket, entry.session)
				await socket.emit(RESUBSCRIBE, {"session": entry.session})


def redis_client() -> redis.asyncio.Redis:
	config = get_config()
	conf = frappe.get_common_site_config(sites_path=config.sites_path)
	return redis.asyncio.from_url(conf.get("flow_redis_url") or config.redis_queue, decode_responses=True)


def parse(data: str) -> dict | None:
	try:
		value = json.loads(data)
	except ValueError:
		return None
	return value if isinstance(value, dict) else None


def is_valid_name(session: object) -> bool:
	return isinstance(session, str) and bool(SESSION_NAME.fullmatch(session))


relay = Relay()


@realtime.on("flow:subscribe")
async def subscribe(socket: Socket, session: object) -> dict:
	try:
		subscribed = await relay.subscribe(socket, session)
	except Exception:
		logger.exception("flow: subscribe failed")
		subscribed = False
	return {"subscribed": subscribed}


@realtime.on("flow:unsubscribe")
async def unsubscribe(socket: Socket, session: object) -> None:
	if is_valid_name(session):
		await relay.release(socket, session)


@realtime.on("disconnect")
async def disconnect(socket: Socket) -> None:
	for session in list(socket.get("flow_sessions", [])):
		await relay.release(socket, session)
