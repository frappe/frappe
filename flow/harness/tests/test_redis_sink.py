import asyncio
import json
from fnmatch import fnmatchcase

import pytest
from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED
from flow_harness.server.redis_sink import RedisEventSink
from flow_harness.server.tenants import Tenant
from flow_harness.session.store import SessionStore


class RecordingRedis:
	def __init__(self):
		self.published: list[tuple[str, dict]] = []
		self.received: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
		self.closed = False

	async def publish(self, channel: str, message: str) -> None:
		item = (channel, json.loads(message))
		self.published.append(item)
		self.received.put_nowait(item)

	async def aclose(self) -> None:
		self.closed = True


class BlockingRedis(RecordingRedis):
	def __init__(self):
		super().__init__()
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.cancelled = False

	async def publish(self, channel: str, message: str) -> None:
		self.started.set()
		try:
			await self.release.wait()
		except asyncio.CancelledError:
			self.cancelled = True
			raise
		await super().publish(channel, message)


async def test_redis_sink_drains_events_in_order_and_keeps_flat_payloads():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		sink("shared", {"site": "site1.localhost", "type": "text_delta", "text": "a"})
		sink("shared", {"site": "site2.localhost", "type": "run_ended", "seq": 3})
		sink("local", {"type": "text_delta", "text": "b"})

	assert client.published == [
		(
			"harness:site1.localhost:shared",
			{"site": "site1.localhost", "session_id": "shared", "type": "text_delta", "text": "a"},
		),
		(
			"harness:site2.localhost:shared",
			{"site": "site2.localhost", "session_id": "shared", "type": "run_ended", "seq": 3},
		),
		("harness:local", {"session_id": "local", "type": "text_delta", "text": "b"}),
	]
	assert client.closed
	sink("local", {"type": "text_delta", "text": "ignored"})
	assert len(client.published) == 3


async def test_sites_drain_in_round_robin_order():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		for site, count in (("busy", 3), ("quiet", 2), (None, 2)):
			for revision in range(1, count + 1):
				sink("shared", {"site": site, "type": "text_delta", "revision": revision})

	assert [(event["site"], event["revision"]) for _, event in client.published] == [
		("busy", 1),
		("quiet", 1),
		(None, 1),
		("busy", 2),
		("quiet", 2),
		(None, 2),
		("busy", 3),
	]


@pytest.mark.parametrize("site", [None, "busy"])
async def test_site_limit_covers_all_its_sessions_and_leaves_room_for_other_sites(site):
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", max_pending=6, max_pending_per_site=2, client=client)
	async with sink.lifespan(None):
		for session_id in ("one", "two", "dropped"):
			sink(session_id, {"site": site, "type": "run_ended", "seq": 3})
		sink("one", {"site": "local", "type": "run_ended", "seq": 3})

	channel = f"harness-resync:site:{site}" if site else "harness-resync:local"
	assert [item for item in client.published if item[1]["type"] == "resync_required"] == [
		(channel, {"type": "resync_required", "session_ids": ["dropped"]})
	]
	assert [(event["site"], event["session_id"]) for _, event in client.published if "site" in event] == [
		(site, "one"),
		("local", "one"),
		(site, "two"),
	]


async def test_default_site_limit_keeps_a_busy_site_from_filling_the_total_capacity():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		for revision in range(1024):
			sink(f"session{revision % 16}", {"site": "busy", "type": "text_delta", "revision": revision})
		sink("shared", {"site": "quiet", "type": "run_ended", "seq": 3})

	assert [event["revision"] for _, event in client.published if event.get("site") == "busy"] == list(
		range(128)
	)
	assert (
		"harness:quiet:shared",
		{"site": "quiet", "session_id": "shared", "type": "run_ended", "seq": 3},
	) in client.published
	assert [channel for channel, event in client.published if event["type"] == "resync_required"] == [
		"harness-resync:site:busy"
	]


async def test_total_limit_still_applies_across_site_queues():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", max_pending=3, max_pending_per_site=2, client=client)
	async with sink.lifespan(None):
		for site in ("first", "first", "second", "third"):
			sink("shared", {"site": site, "type": "run_ended", "seq": 3})

	assert [event["site"] for _, event in client.published if "site" in event] == ["first", "second", "first"]
	assert [channel for channel, event in client.published if event["type"] == "resync_required"] == [
		"harness-resync:site:third"
	]


async def test_draining_releases_capacity_and_wakes_for_new_events():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, max_pending_per_site=1, client=client)
	async with sink.lifespan(None):
		for site in ("first", "first", "second", "first"):
			sink("shared", {"site": site, "type": "run_ended", "seq": 3})
			assert await asyncio.wait_for(client.received.get(), 1) == (
				f"harness:{site}:shared",
				{"site": site, "session_id": "shared", "type": "run_ended", "seq": 3},
			)


async def test_a_site_joining_during_publish_does_not_wait_for_the_busy_site_to_drain():
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		for revision in range(4):
			sink("shared", {"site": "busy", "type": "text_delta", "revision": revision})
		await asyncio.wait_for(client.started.wait(), 1)
		sink("shared", {"site": "quiet", "type": "run_ended", "seq": 3})
		client.release.set()

	assert [event["site"] for _, event in client.published] == ["busy", "busy", "quiet", "busy", "busy"]
	assert [event["revision"] for _, event in client.published if event["site"] == "busy"] == [0, 1, 2, 3]


async def test_sites_keep_fifo_order_across_sessions():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		for site in range(8):
			for session in range(16):
				for revision in range(4):
					sink(str(session), {"site": str(site), "type": "text_delta", "revision": revision})

	assert [(e["site"], e["session_id"], e["revision"]) for _, e in client.published] == [
		(str(site), str(session), revision)
		for session in range(16)
		for revision in range(4)
		for site in range(8)
	]


@pytest.mark.parametrize("name", ["max_pending", "max_pending_per_site"])
@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_pending_limits_must_be_positive(name, limit):
	with pytest.raises(ValueError, match=f"{name} must be a positive integer"):
		RedisEventSink("redis://unused", client=RecordingRedis(), **{name: limit})


async def test_overflow_does_not_block_the_loop_and_signals_a_dropped_terminal_event():
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("one", {"type": "text_delta", "text": "a"})
		await asyncio.wait_for(client.started.wait(), 1)
		sink("one", {"type": "text_delta", "text": "b"})
		sink("one", {"site": "site1.localhost", "type": "run_ended", "seq": 3})
		assert not client.release.is_set()
		client.release.set()
		async with asyncio.timeout(2):
			messages = [await client.received.get() for _ in range(3)]

	assert (
		"harness-resync:site:site1.localhost",
		{"type": "resync_required", "session_ids": ["one"]},
	) in messages
	assert [message["text"] for _, message in messages if message["type"] == "text_delta"] == ["a", "b"]
	assert all(message["type"] != "run_ended" for _, message in messages)


@pytest.mark.parametrize(
	("site", "channel"),
	[
		(None, "harness-resync:local"),
		("site1.localhost", "harness-resync:site:site1.localhost"),
	],
)
async def test_redis_sink_retries_resync_without_new_events(monkeypatch, caplog, site, channel):
	monkeypatch.setattr("flow_harness.server.redis_sink._RETRY_SECONDS", 0.01)

	class OfflineRedis(RecordingRedis):
		def __init__(self):
			super().__init__()
			self.marker_failed = asyncio.Event()
			self.online = False

		async def publish(self, channel: str, message: str) -> None:
			if not self.online:
				if json.loads(message)["type"] == "resync_required":
					self.marker_failed.set()
				raise ConnectionError("do-not-log-credentials")
			await super().publish(channel, message)

	client = OfflineRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		sink("one", {"site": site, "type": "run_ended", "seq": 3})
		await asyncio.wait_for(client.marker_failed.wait(), 1)
		client.online = True
		assert await asyncio.wait_for(client.received.get(), 2) == (
			channel,
			{"type": "resync_required", "session_ids": ["one"]},
		)

	assert "Redis event publishing failed" in caplog.text
	assert "do-not-log-credentials" not in caplog.text


@pytest.mark.parametrize("invalid_kind", ["object", "circular"])
async def test_serialization_errors_do_not_stop_publishing_or_mark_redis_offline(caplog, invalid_kind):
	caplog.set_level("INFO", logger="flow")
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	invalid = {"site": "first", "type": "text_delta"}
	invalid["text"] = invalid if invalid_kind == "circular" else object()
	async with sink.lifespan(None):
		sink("broken", invalid)
		sink("healthy", {"site": "second", "type": "text_delta", "text": "ok"})
		async with asyncio.timeout(1):
			messages = [await client.received.get() for _ in range(2)]

	assert messages == [
		("harness-resync:site:first", {"type": "resync_required", "session_ids": ["broken"]}),
		(
			"harness:second:healthy",
			{"site": "second", "session_id": "healthy", "type": "text_delta", "text": "ok"},
		),
	]
	assert "Redis event serialization failed" in caplog.text
	assert "Redis event publishing failed" not in caplog.text
	assert "Redis event publishing recovered" not in caplog.text


@pytest.mark.parametrize("site_count", [2, 3])
async def test_resync_targets_affected_sites_and_falls_back_at_the_limit(monkeypatch, site_count):
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SITES", 2)
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("shared", {"site": "healthy", "type": "text_delta", "text": "a"})
		await asyncio.wait_for(client.started.wait(), 1)
		sink("shared", {"site": "healthy", "type": "text_delta", "text": "b"})
		for _ in range(3):
			for number in range(site_count):
				sink("shared", {"site": f"site{number}", "type": "run_ended", "seq": 3})
		client.release.set()

	notifications = [channel for channel, event in client.published if event["type"] == "resync_required"]
	expected = (
		{"harness-resync:site:site0", "harness-resync:site:site1"}
		if site_count == 2
		else {"harness-resync:all"}
	)
	assert set(notifications) == expected
	assert len(notifications) == len(expected)
	assert all(fnmatchcase(channel, "harness-resync:*") for channel in notifications)
	for _, event in client.published:
		if event["type"] == "resync_required":
			assert event == (
				{"type": "resync_required", "session_ids": ["shared"]}
				if site_count == 2
				else {"type": "resync_required"}
			)


@pytest.mark.parametrize("site", [None, "first"])
@pytest.mark.parametrize("session_count", [2, 3])
async def test_resync_deduplicates_sessions_and_falls_back_only_for_their_site(
	monkeypatch, site, session_count
):
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SESSIONS", 2)
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("accepted", {"site": site, "type": "run_ended", "seq": 1})
		for _ in range(3):
			for number in range(session_count):
				sink(f"session{number}", {"site": site, "type": "run_ended", "seq": 1})
		sink("separate", {"site": "second", "type": "run_ended", "seq": 1})

	channel = f"harness-resync:site:{site}" if site else "harness-resync:local"
	notices = {channel: e for channel, e in client.published if e["type"] == "resync_required"}
	assert notices == {
		channel: (
			{"type": "resync_required", "session_ids": ["session0", "session1"]}
			if session_count == 2
			else {"type": "resync_required"}
		),
		"harness-resync:site:second": {"type": "resync_required", "session_ids": ["separate"]},
	}


async def test_resync_names_do_not_collide_with_sites_or_session_channels():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", max_pending=3, client=client)
	sites = ("all", "local", "site", "control", "resync")
	async with sink.lifespan(None):
		sink("all", {"site": "resync", "type": "text_delta", "text": "a"})
		sink("local", {"site": "resync", "type": "text_delta", "text": "b"})
		sink("resync", {"type": "text_delta", "text": "c"})
		for site in (None, *sites):
			sink("shared", {"site": site, "type": "run_ended", "seq": 3})

	notifications = [channel for channel, event in client.published if event["type"] == "resync_required"]
	assert set(notifications) == {
		"harness-resync:local",
		*(f"harness-resync:site:{site}" for site in sites),
	}
	assert len(notifications) == len(sites) + 1
	assert {channel for channel, event in client.published if event["type"] == "text_delta"} == {
		"harness:resync:all",
		"harness:resync:local",
		"harness:resync",
	}
	for channel, event in client.published:
		assert fnmatchcase(channel, "harness-resync:*") == (event["type"] == "resync_required")


async def test_resync_retries_the_unsent_sites_after_a_partial_failure(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._RETRY_SECONDS", 0.01)

	class RecoveringRedis(BlockingRedis):
		def __init__(self):
			super().__init__()
			self.sent_first = False
			self.failed = asyncio.Event()
			self.online = False

		async def publish(self, channel, message):
			if json.loads(message)["type"] == "resync_required":
				if self.sent_first and not self.online:
					self.failed.set()
					raise ConnectionError("offline")
				self.sent_first = True
			await super().publish(channel, message)

	client = RecoveringRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("one", {"type": "text_delta", "text": "a"})
		await asyncio.wait_for(client.started.wait(), 1)
		sink("one", {"type": "text_delta", "text": "b"})
		for site in ("first", "second", "third"):
			sink("one", {"site": site, "type": "run_ended", "seq": 3})
		client.release.set()
		await asyncio.wait_for(client.failed.wait(), 1)
		client.online = True
		async with asyncio.timeout(2):
			messages = [await client.received.get() for _ in range(5)]

	assert {channel for channel, event in messages if event["type"] == "resync_required"} == {
		f"harness-resync:site:{site}" for site in ("first", "second", "third")
	}
	assert all(event["session_ids"] == ["one"] for _, event in messages if event["type"] == "resync_required")


async def test_failed_resync_merges_new_sessions_and_keeps_the_site_fallback(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SESSIONS", 2)
	monkeypatch.setattr("flow_harness.server.redis_sink._RETRY_SECONDS", 0.01)

	class FailingResyncRedis(RecordingRedis):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def publish(self, channel, message):
			if json.loads(message)["type"] == "resync_required" and not self.started.is_set():
				self.started.set()
				await self.release.wait()
				raise ConnectionError("offline")
			await super().publish(channel, message)

	client = FailingResyncRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("accepted", {"site": "first", "type": "run_ended", "seq": 1})
		sink("one", {"site": "first", "type": "run_ended", "seq": 1})
		await asyncio.wait_for(client.started.wait(), 1)
		for sid in ("two", "three"):
			sink(sid, {"site": "first", "type": "run_ended", "seq": 1})
		sink("unrelated", {"site": "second", "type": "run_ended", "seq": 1})
		client.release.set()
		async with asyncio.timeout(1):
			messages = [await client.received.get() for _ in range(3)]

	assert {channel: e for channel, e in messages if e["type"] == "resync_required"} == {
		"harness-resync:site:first": {"type": "resync_required"},
		"harness-resync:site:second": {"type": "resync_required", "session_ids": ["unrelated"]},
	}


async def test_new_drop_during_resync_gets_another_notification(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._RETRY_SECONDS", 0.01)

	class PausedResyncRedis(BlockingRedis):
		def __init__(self):
			super().__init__()
			self.resync_started = asyncio.Event()
			self.resync_release = asyncio.Event()

		async def publish(self, channel, message):
			if json.loads(message)["type"] == "resync_required":
				self.resync_started.set()
				await self.resync_release.wait()
			await super().publish(channel, message)

	client = PausedResyncRedis()
	sink = RedisEventSink("redis://unused", max_pending=1, client=client)
	async with sink.lifespan(None):
		sink("one", {"type": "text_delta", "text": "a"})
		await asyncio.wait_for(client.started.wait(), 1)
		sink("one", {"type": "text_delta", "text": "b"})
		sink("one", {"site": "first", "type": "text_delta", "text": "dropped"})
		client.release.set()
		await asyncio.wait_for(client.resync_started.wait(), 1)
		for sid in ("two", "three"):
			sink(sid, {"site": "first", "type": "run_ended", "seq": 3})
		client.resync_release.set()
		resyncs = []
		async with asyncio.timeout(2):
			while len(resyncs) < 2:
				channel, event = await client.received.get()
				if event["type"] == "resync_required":
					resyncs.append((channel, event))

	assert resyncs == [
		("harness-resync:site:first", {"type": "resync_required", "session_ids": ["one"]}),
		("harness-resync:site:first", {"type": "resync_required", "session_ids": ["three", "two"]}),
	]


async def test_shutdown_cancels_a_stalled_publish_and_closes_redis(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._SHUTDOWN_SECONDS", 0.05)
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with asyncio.timeout(0.5):
		async with sink.lifespan(None):
			sink("one", {"type": "text_delta", "text": "a"})
			await client.started.wait()
	assert client.cancelled
	assert client.closed


async def test_connection_cleanup_has_a_deadline(monkeypatch, caplog):
	monkeypatch.setattr("flow_harness.server.redis_sink._CLOSE_SECONDS", 0.01)

	class StalledCloseRedis(RecordingRedis):
		async def aclose(self):
			try:
				await asyncio.Event().wait()
			finally:
				self.closed = True

	client = StalledCloseRedis()
	async with asyncio.timeout(0.5):
		async with RedisEventSink("redis://unused", client=client).lifespan(None):
			pass
	assert client.closed
	assert "Redis connection cleanup failed (TimeoutError)" in caplog.text


async def test_lifespan_closes_redis_when_the_server_fails():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	with pytest.raises(RuntimeError, match="server failed"):
		async with sink.lifespan(None):
			raise RuntimeError("server failed")
	assert client.closed


async def test_lifespan_cancellation_leaves_no_publisher_running(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._SHUTDOWN_SECONDS", 0.01)
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", client=client)

	async def serve():
		async with sink.lifespan(None):
			sink("one", {"type": "text_delta", "text": "a"})
			await asyncio.Event().wait()

	task = asyncio.create_task(serve())
	try:
		await asyncio.wait_for(client.started.wait(), 1)
	finally:
		task.cancel()
		with pytest.raises(asyncio.CancelledError):
			await asyncio.wait_for(task, 0.5)
	assert client.cancelled
	assert client.closed


async def test_lifespan_refuses_a_second_worker():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		with pytest.raises(RuntimeError, match="already started"):
			async with sink.lifespan(None):
				pytest.fail("started a second worker")
	assert client.closed


def test_server_lifespan_publishes_tenant_events_and_closes_redis(tmp_path):
	redis = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=redis)
	store = SessionStore(
		str(tmp_path / "data"),
		event_sink=sink,
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
		tool_allowlist=DEPLOYED.tool_allowlist,
	)
	app = create_app(
		store,
		policy=DEPLOYED,
		tenants=[Tenant(site="one", token="first"), Tenant(site="two", token="second")],
		lifespan=sink.lifespan,
	)
	with TestClient(app) as client:
		for token in ("first", "second"):
			headers = {"Authorization": f"Bearer {token}"}
			assert (
				client.post(
					"/sessions",
					json={"model": "mock", "cwd": str(tmp_path), "session_id": "shared"},
					headers=headers,
				).status_code
				== 200
			)
			assert (
				client.post(
					"/sessions/shared/run",
					params={"wait": "true"},
					json={"message": "hello"},
					headers=headers,
				).status_code
				== 200
			)

	assert redis.closed
	assert {channel for channel, _event in redis.published} == {"harness:one:shared", "harness:two:shared"}
	for site in ("one", "two"):
		events = [event for _channel, event in redis.published if event["site"] == site]
		assert events[-1]["type"] == "run_ended"
		assert [event["revision"] for event in events] == list(range(1, len(events) + 1))
