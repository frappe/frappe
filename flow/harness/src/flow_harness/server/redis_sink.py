"""Non-blocking Redis event publishing."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Protocol

_RESYNC_CHANNEL = "harness-resync:all"
_MAX_RESYNC_SITES = 1024
_MAX_RESYNC_SESSIONS = 128
_SHUTDOWN_SECONDS = 2.0
_CLOSE_SECONDS = 0.5
_RETRY_SECONDS = 1.0


class _RedisClient(Protocol):
	def publish(self, channel: str, message: str) -> Awaitable[object]: ...

	def aclose(self) -> Awaitable[None]: ...


class RedisEventSink:
	def __init__(
		self,
		url: str,
		*,
		max_pending: int = 1024,
		max_pending_per_site: int = 128,
		client: _RedisClient | None = None,
	):
		for name, limit in (
			("max_pending", max_pending),
			("max_pending_per_site", max_pending_per_site),
		):
			if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
				raise ValueError(f"{name} must be a positive integer")
		if client is None:
			import redis.asyncio as redis
			from redis.asyncio.retry import Retry
			from redis.backoff import NoBackoff

			client = redis.from_url(
				url, socket_connect_timeout=0.5, socket_timeout=0.5, retry=Retry(NoBackoff(), 0)
			)
		self._client = client
		self._max_pending = max_pending
		self._max_pending_per_site = max_pending_per_site
		self._pending: OrderedDict[str | None, deque[tuple[str, dict]]] = OrderedDict()
		self._queued_event_count = 0
		self._publisher_wakeup = asyncio.Event()
		self._lifespan_started = False
		self._shutdown_requested = False
		self._resync_channels: dict[str, set[str] | None] = {}
		self._publish_failed = False

	def __call__(self, session_id: str, event: dict) -> None:
		if self._shutdown_requested:
			return
		site = event.get("site") or None
		pending_for_site = self._pending.get(site)
		if self._queued_event_count >= self._max_pending or (
			pending_for_site is not None and len(pending_for_site) >= self._max_pending_per_site
		):
			channel = _resync_channel(site)
			if channel not in self._resync_channels and _RESYNC_CHANNEL not in self._resync_channels:
				logging.getLogger("flow").warning("Redis event queue full; requesting resync on %s", channel)
			self._queue_resync(channel, {session_id})
			return
		if pending_for_site is None:
			pending_for_site = self._pending[site] = deque()
		pending_for_site.append((session_id, event))
		self._queued_event_count += 1
		self._publisher_wakeup.set()

	@asynccontextmanager
	async def lifespan(self, _app: object) -> AsyncIterator[None]:
		if self._lifespan_started:
			raise RuntimeError("Redis sink already started")
		self._lifespan_started = True
		task = asyncio.create_task(self._run(), name="redis-event-sink")
		try:
			yield
		finally:
			self._shutdown_requested = True
			self._publisher_wakeup.set()
			try:
				await asyncio.wait_for(task, _SHUTDOWN_SECONDS)
			except TimeoutError:
				pass
			finally:
				try:
					await asyncio.wait_for(self._client.aclose(), _CLOSE_SECONDS)
				except Exception as error:
					logging.getLogger("flow").warning(
						"Redis connection cleanup failed (%s)", type(error).__name__
					)

	async def _run(self) -> None:
		loop = asyncio.get_running_loop()
		next_resync = 0.0
		while True:
			if self._resync_channels and (loop.time() >= next_resync or self._shutdown_requested):
				await self._flush_resync()
				next_resync = loop.time() + _RETRY_SECONDS
			if self._publish_failed:
				if self._shutdown_requested:
					return
				await asyncio.sleep(max(0, next_resync - loop.time()))
				continue
			timeout = max(0, next_resync - loop.time()) if self._resync_channels else None
			try:
				async with asyncio.timeout(timeout):
					item = await self._next_event()
			except TimeoutError:
				continue
			if item is None:
				return
			session_id, event = item
			site = event.get("site")
			channel = f"harness:{site}:{session_id}" if site else f"harness:{session_id}"
			if not await self._publish(channel, {**event, "session_id": session_id}):
				self._queue_resync(_resync_channel(site), {session_id})

	async def _next_event(self) -> tuple[str, dict] | None:
		while not self._pending:
			if self._shutdown_requested:
				return None
			self._publisher_wakeup.clear()
			await self._publisher_wakeup.wait()
		site, pending = self._pending.popitem(last=False)
		event = pending.popleft()
		if pending:
			self._pending[site] = pending
		self._queued_event_count -= 1
		return event

	async def _flush_resync(self) -> None:
		channels, self._resync_channels = self._resync_channels, {}
		while channels:
			channel, session_ids = channels.popitem()
			message: dict = {"type": "resync_required"}
			if session_ids is not None:
				message["session_ids"] = sorted(session_ids)
			if not await self._publish(channel, message):
				self._queue_resync(channel, session_ids)
				for remaining, sessions in channels.items():
					self._queue_resync(remaining, sessions)
				return

	def _queue_resync(self, channel: str, session_ids: set[str] | None) -> None:
		if _RESYNC_CHANNEL in self._resync_channels:
			return
		if channel == _RESYNC_CHANNEL or (
			channel not in self._resync_channels and len(self._resync_channels) >= _MAX_RESYNC_SITES
		):
			self._resync_channels = {_RESYNC_CHANNEL: None}
			return
		pending = self._resync_channels.setdefault(channel, set())
		if pending is None:
			return
		if session_ids is None:
			self._resync_channels[channel] = None
			return
		pending.update(session_ids)
		if len(pending) > _MAX_RESYNC_SESSIONS:
			self._resync_channels[channel] = None

	async def _publish(self, channel: str, message: dict) -> bool:
		logger = logging.getLogger("flow")
		try:
			payload = json.dumps(message, separators=(",", ":"))
		except (TypeError, ValueError, RecursionError):
			logger.exception("Redis event serialization failed")
			return False
		try:
			await self._client.publish(channel, payload)
		except Exception as error:
			if not self._publish_failed:
				logger.warning("Redis event publishing failed (%s)", type(error).__name__)
			self._publish_failed = True
			return False
		if self._publish_failed:
			logger.info("Redis event publishing recovered")
		self._publish_failed = False
		return True


def _resync_channel(site: str | None) -> str:
	return f"harness-resync:site:{site}" if site else "harness-resync:local"
