import asyncio
import json
from fnmatch import fnmatchcase

import pytest
from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED
from flow_harness.server.redis_sink import RedisEventSink
from flow_harness.server.tenants import TenantTemplate
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
	sink = RedisEventSink("redis://unused", max_pending=1, max_pending_per_site=1, client=client)
	async with sink.lifespan(None):
		for session_id, event in (
			("shared", {"site": "site1.localhost", "type": "text_delta", "text": "a"}),
			("shared", {"site": "site1.localhost", "type": "run_ended", "seq": 3}),
			("shared", {"site": "site2.localhost", "type": "run_ended", "seq": 3}),
			("local", {"type": "text_delta", "text": "b"}),
		):
			sink(session_id, event)  # fits only because the publisher drained the one before
			await asyncio.wait_for(client.received.get(), 1)

	assert client.published == [
		(
			"harness:site1.localhost:shared",
			{"site": "site1.localhost", "session_id": "shared", "type": "text_delta", "text": "a"},
		),
		(
			"harness:site1.localhost:shared",
			{"site": "site1.localhost", "session_id": "shared", "type": "run_ended", "seq": 3},
		),
		(
			"harness:site2.localhost:shared",
			{"site": "site2.localhost", "session_id": "shared", "type": "run_ended", "seq": 3},
		),
		("harness:local", {"session_id": "local", "type": "text_delta", "text": "b"}),
	]
	assert client.closed
	sink("local", {"type": "text_delta", "text": "ignored"})
	assert len(client.published) == 4


async def test_sites_take_turns_and_each_keeps_fifo_order():
	client = BlockingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	async with sink.lifespan(None):
		for session in ("a", "b"):
			for revision in (1, 2):
				sink(session, {"site": "busy", "type": "text_delta", "revision": revision})
		await asyncio.wait_for(client.started.wait(), 1)  # publishing busy's first event
		for site in ("quiet", None):  # join while busy still has a backlog
			for revision in (1, 2):
				sink("a", {"site": site, "type": "text_delta", "revision": revision})
		client.release.set()

	assert [(e["site"], e["session_id"], e["revision"]) for _, e in client.published] == [
		("busy", "a", 1),
		("busy", "a", 2),
		("quiet", "a", 1),
		(None, "a", 1),
		("busy", "b", 1),
		("quiet", "a", 2),
		(None, "a", 2),
		("busy", "b", 2),
	]


async def test_pending_limits_hold_per_site_and_in_total():
	for site in (None, "busy"):
		client = RecordingRedis()
		sink = RedisEventSink("redis://unused", max_pending=3, max_pending_per_site=2, client=client)
		async with sink.lifespan(None):
			for session_id in ("one", "two", "dropped"):  # the site limit covers all its sessions
				sink(session_id, {"site": site, "type": "run_ended", "seq": 3})
			sink("one", {"site": "local", "type": "run_ended", "seq": 3})  # room is left for another site
			sink("one", {"site": "third", "type": "run_ended", "seq": 3})  # but not past the total

		channel = f"harness-resync:site:{site}" if site else "harness-resync:local"
		assert {name: event for name, event in client.published if event["type"] == "resync_required"} == {
			channel: {"type": "resync_required", "session_ids": ["dropped"]},
			"harness-resync:site:third": {"type": "resync_required", "session_ids": ["one"]},
		}, site
		assert [(event["site"], event["session_id"]) for _, event in client.published if "site" in event] == [
			(site, "one"),
			("local", "one"),
			(site, "two"),
		], site


def test_pending_limits_must_be_positive():
	for name in ("max_pending", "max_pending_per_site"):
		for limit in (0, -1, True, 1.5):
			with pytest.raises(ValueError, match=f"{name} must be a positive integer"):
				RedisEventSink("redis://unused", client=RecordingRedis(), **{name: limit})


async def test_serialization_errors_do_not_stop_publishing_or_mark_redis_offline(caplog):
	caplog.set_level("INFO", logger="flow")
	for invalid_kind in ("object", "circular"):
		caplog.clear()
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
		], invalid_kind
		assert "Redis event serialization failed" in caplog.text, invalid_kind
		assert "Redis event publishing failed" not in caplog.text, invalid_kind
		assert "Redis event publishing recovered" not in caplog.text, invalid_kind


async def test_resync_names_dropped_sessions_and_falls_back_past_the_limits(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SITES", 2)
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SESSIONS", 2)
	cases = (
		# within both limits: one notice per site, naming its sessions
		(
			[(None, "session0"), (None, "session1"), ("second", "separate")],
			{
				"harness-resync:local": {"type": "resync_required", "session_ids": ["session0", "session1"]},
				"harness-resync:site:second": {"type": "resync_required", "session_ids": ["separate"]},
			},
		),
		# too many sessions: only that site falls back to a site-wide notice
		(
			[("first", "session0"), ("first", "session1"), ("first", "session2"), ("second", "separate")],
			{
				"harness-resync:site:first": {"type": "resync_required"},
				"harness-resync:site:second": {"type": "resync_required", "session_ids": ["separate"]},
			},
		),
		# too many sites: one notice for everything
		(
			[("site0", "shared"), ("site1", "shared"), ("site2", "shared")],
			{"harness-resync:all": {"type": "resync_required"}},
		),
	)
	for drops, expected in cases:
		client = RecordingRedis()
		sink = RedisEventSink("redis://unused", max_pending=1, client=client)
		async with sink.lifespan(None):
			sink("accepted", {"type": "text_delta", "text": "a"})  # fills the queue
			for _ in range(3):  # repeated drops are deduplicated
				for site, session_id in drops:
					sink(session_id, {"site": site, "type": "run_ended", "seq": 1})

		notices = [
			(channel, event) for channel, event in client.published if event["type"] == "resync_required"
		]
		assert dict(notices) == expected, drops
		assert len(notices) == len(expected), drops


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


async def test_resync_retries_the_unsent_sites_after_a_failure(monkeypatch, caplog):
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
					raise ConnectionError("do-not-log-credentials")
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
		client.online = True  # retried on a timer, with no new events
		async with asyncio.timeout(2):
			messages = [await client.received.get() for _ in range(5)]

	assert {channel for channel, event in messages if event["type"] == "resync_required"} == {
		f"harness-resync:site:{site}" for site in ("first", "second", "third")
	}
	assert all(event["session_ids"] == ["one"] for _, event in messages if event["type"] == "resync_required")
	assert "Redis event publishing failed" in caplog.text
	assert "do-not-log-credentials" not in caplog.text


async def test_drops_during_a_resync_are_notified_after_it(monkeypatch):
	monkeypatch.setattr("flow_harness.server.redis_sink._MAX_RESYNC_SESSIONS", 2)
	monkeypatch.setattr("flow_harness.server.redis_sink._RETRY_SECONDS", 0.01)

	class PausedResyncRedis(RecordingRedis):
		"""Holds the first resync until released, then fails or sends it."""

		def __init__(self, fails):
			super().__init__()
			self.fails = fails
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def publish(self, channel, message):
			if json.loads(message)["type"] == "resync_required" and not self.started.is_set():
				self.started.set()
				await self.release.wait()
				if self.fails:
					raise ConnectionError("offline")
			await super().publish(channel, message)

	expected = {
		# a failed notice merges with the new drops, here past the session limit
		True: {"harness-resync:site:first": [None], "harness-resync:site:second": [["unrelated"]]},
		# a sent one is followed by another that names only the new drops
		False: {
			"harness-resync:site:first": [["one"], ["three", "two"]],
			"harness-resync:site:second": [["unrelated"]],
		},
	}
	for fails, notices in expected.items():
		client = PausedResyncRedis(fails)
		sink = RedisEventSink("redis://unused", max_pending=1, client=client)
		async with sink.lifespan(None):
			sink("accepted", {"site": "first", "type": "run_ended", "seq": 1})
			sink("one", {"site": "first", "type": "run_ended", "seq": 1})
			await asyncio.wait_for(client.started.wait(), 1)
			for sid in ("two", "three"):
				sink(sid, {"site": "first", "type": "run_ended", "seq": 1})
			sink("unrelated", {"site": "second", "type": "run_ended", "seq": 1})
			client.release.set()
			count = sum(len(sent) for sent in notices.values())
			async with asyncio.timeout(2):
				while sum(event["type"] == "resync_required" for _, event in client.published) < count:
					await client.received.get()

		resyncs: dict[str, list] = {}
		for channel, event in client.published:
			if event["type"] == "resync_required":
				resyncs.setdefault(channel, []).append(event.get("session_ids"))
		assert resyncs == notices, fails


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


async def test_lifespan_refuses_a_second_worker_and_closes_redis_when_the_server_fails():
	client = RecordingRedis()
	sink = RedisEventSink("redis://unused", client=client)
	with pytest.raises(RuntimeError, match="already started"):
		async with sink.lifespan(None):
			async with sink.lifespan(None):  # its refusal fails the server
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
	for site, token in (("one", "first"), ("two", "second")):
		(tmp_path / "sites" / site).mkdir(parents=True)
		(tmp_path / "sites" / site / "site.json").write_text(json.dumps({"token": token}))
	app = create_app(
		store,
		policy=DEPLOYED,
		tenants=TenantTemplate(
			token_file=str(tmp_path / "sites" / "{site}" / "site.json"), token_key="token"
		),
		lifespan=sink.lifespan,
	)
	with TestClient(app) as client:
		for site, token in (("one", "first"), ("two", "second")):
			headers = {"Authorization": f"Bearer {token}", "X-Flow-Site": site}
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
