"""The session layer: disk store, derived lifecycle state, crash repair at load,
and the live event surface."""

import asyncio
import json
import os
import re
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from flow_harness.agent.client_tools import notify_run_ended
from flow_harness.events import (
	AssistantMessage,
	RunEnded,
	RunStarted,
	TextDelta,
	ThinkingDelta,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.mock import MockModel
from flow_harness.session.config import SessionConfig
from flow_harness.session.session import INTERRUPTED, RewindError, SessionConflict, SessionState
from flow_harness.session.store import SessionStore
from flow_harness.session.transcript import active_path


def test_store_create_and_reload(tmp_path):
	data_dir = tmp_path / "state"
	store = SessionStore(str(data_dir))
	session = store.create(SessionConfig(model="mock"))
	session.log.append(UserMessage(content="remember me"))

	fresh = SessionStore(str(data_dir))  # cold store, only disk
	reloaded = fresh.get(session.id)
	assert reloaded.config.model == "mock"
	assert reloaded.transcript.messages[0].content == "remember me"
	assert oct(os.stat(data_dir).st_mode & 0o777) == "0o700"
	assert oct(os.stat(store.sessions_dir).st_mode & 0o777) == "0o700"
	assert oct(os.stat(reloaded.log.path).st_mode & 0o777) == "0o600"


def test_store_groups_sessions_by_project_and_delete_prunes_only_empty_dirs(tmp_path):
	data_dir = tmp_path / "state"
	first_project = tmp_path / "workspace-a" / "app"
	second_project = tmp_path / "workspace-b" / "app"  # same basename, different path
	first_project.mkdir(parents=True)
	second_project.mkdir(parents=True)
	store = SessionStore(str(data_dir))

	first = store.create(SessionConfig(cwd=str(first_project)))
	second = store.create(SessionConfig(cwd=str(first_project)))
	other = store.create(SessionConfig(cwd=str(second_project)))
	first_dir = Path(first.log.path).parent
	second_dir = Path(second.log.path).parent
	other_dir = Path(other.log.path).parent

	assert first_dir == second_dir
	assert first_dir != other_dir
	assert first_dir.parent == other_dir.parent == Path(store.sessions_dir)
	assert re.fullmatch(r"app--[0-9a-f]{12}", first_dir.name)
	assert oct(first_dir.stat().st_mode & 0o777) == "0o700"
	assert first.attachment_store is not None
	assert Path(first.attachment_store.path).parent == first_dir
	assert {path.name for path in Path(store.sessions_dir).iterdir()} == {
		first_dir.name,
		other_dir.name,
	}

	(Path(first.attachment_store.path) / "marker").write_text("bytes")
	first.run_end_marker.touch()
	store.delete(first.id)

	assert first_dir.is_dir()
	assert not Path(first.log.path).exists()
	assert not Path(first.attachment_store.path).exists()
	assert not first.run_end_marker.exists()
	assert store.get(second.id) is second

	store.delete(second.id)
	assert not first_dir.exists()


def test_store_refuses_unsafe_ids_fenced_cwds_and_tampered_meta(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(allowed)])
	session = store.create(SessionConfig(model="mock", cwd=str(allowed)))
	assert session.config.cwd == str(allowed)

	with pytest.raises(ValueError, match="invalid session_id"):
		store.create(SessionConfig(session_id="../../etc/x", cwd=str(allowed)))
	with pytest.raises(ValueError, match="not under an allowed root"):
		store.create(SessionConfig(cwd=str(tmp_path)))

	# the config schema is closed: a meta file with fields the daemon never wrote fails loudly
	meta = Path(session.log.path).with_name(f"{session.id}.meta.json")
	config = json.loads(meta.read_text())
	config["injected_field"] = "injected-secret"
	meta.write_text(json.dumps(config))
	with pytest.raises(ValidationError):
		SessionStore(str(tmp_path / "data"), allowed_roots=[str(allowed)]).get(session.id)


async def test_set_model_applies_to_later_runs_and_survives_restart(tmp_path, monkeypatch):
	resolved = []

	def spy(name, **kwargs):
		resolved.append(name)
		return MockModel()

	monkeypatch.setattr("flow_harness.agent.loop.get_model", spy)
	credentials = CredentialStore(str(tmp_path / "credentials.json"))  # keep auth offline
	store = SessionStore(str(tmp_path), credential_store=credentials)
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path)))

	with pytest.raises(ValueError, match="non-empty"):
		await session.set_model("")
	assert session.log.latest_seq == 0  # nothing became durable

	await session.set_model("mock/v2", credential_id="mock-profile")
	seq_after_change = session.log.latest_seq
	await session.set_model("mock/v2", credential_id="mock-profile")  # same selection: no event
	assert session.log.latest_seq == seq_after_change

	handle = await session.run("hi")
	assert handle.task is not None
	await handle.task
	assert resolved == ["mock/v2"]
	assert (session.model, session.credential_id) == ("mock/v2", "mock-profile")

	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert (reloaded.model, reloaded.credential_id) == ("mock/v2", "mock-profile")
	assert reloaded.config.model == "mock"  # the creation config never mutates


def test_reload_closes_a_crashed_run_once(tmp_path):
	"""A daemon that died mid-turn left tool calls with no results and its run open.
	Loading the session closes both durably — once — so providers accept the transcript."""
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.log.append(RunStarted(run_id="r1"))
	session.log.append(UserMessage(content="go"))
	session.log.append(
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="subagent", arguments={"task": "look"}),
				ToolCall(id="c2", name="read", arguments={"path": "b.txt"}),
			]
		)
	)
	session.log.append(RunStarted(run_id="r2", subagent_id="c1"))
	session.log.append(RunEnded(reason="done", subagent_id="c1"))  # only the sub-agent's run ended
	session.log.append(ToolResult(tool_call_id="c2", name="read", content="second result"))
	crashed_seq = session.log.latest_seq

	reloaded = SessionStore(str(tmp_path)).get(session.id)

	rows = reloaded.log.read_since(crashed_seq)
	assert [row["type"] for row in rows] == ["tool_result", "run_error", "run_ended"]
	assert rows[0]["tool_call_id"] == "c1"
	assert rows[0]["is_error"] is True
	assert rows[0]["details"]["repair"] == "interrupted"
	assert (rows[1]["message"], rows[2]["reason"]) == (INTERRUPTED, "error")
	# position places the repair beside its call, in the order the calls were made
	assert [message.type for message in reloaded.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	assert [m.tool_call_id for m in reloaded.transcript.messages[2:]] == ["c1", "c2"]
	assert reloaded.transcript.messages[3].content == "second result"
	assert SessionStore(str(tmp_path)).get(session.id).log.latest_seq == rows[-1]["seq"]  # only once


async def test_commit_failure_fails_the_task_and_frees_the_session(tmp_path, monkeypatch):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	original_append = session.log.append

	def fail_terminal(event):
		if isinstance(event, RunEnded):
			raise OSError("log unavailable")
		return original_append(event)

	monkeypatch.setattr(session.log, "append", fail_terminal)
	handle = await session.run("hi", model=MockModel(replies=[AssistantMessage(content="ok")]))
	assert handle.task is not None

	with pytest.raises(OSError, match="log unavailable"):
		await handle.task
	assert session.is_running is False


class _Blocking(MockModel):
	"""Blocks inside its model call until released (or aborted)."""

	def __init__(self, replies=None):
		super().__init__(replies=replies)
		self.started = asyncio.Event()
		self.release = asyncio.Event()

	async def run(self, request):
		self.started.set()
		await self.release.wait()
		async for event in super().run(request):
			yield event


async def test_a_running_session_refuses_rewind_model_changes_and_compaction(tmp_path):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock", cwd=str(tmp_path)))
	assert session.state is SessionState.IDLE
	with pytest.raises(SessionConflict, match="nothing to compact"):
		await session.compact()

	model = _Blocking()
	handle = await session.run("go", model=model)
	await model.started.wait()
	assert session.state is SessionState.RUNNING  # derived from the live task

	with pytest.raises(SessionConflict):
		await session.rewind(1)
	with pytest.raises(SessionConflict):
		await session.set_model("mock/v2")
	with pytest.raises(SessionConflict, match="already active"):
		await session.compact()

	model.release.set()
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.IDLE
	assert session.model == "mock"


async def test_a_paused_session_holds_its_batch_until_resumed_or_cancelled(tmp_path):
	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path), confirm_tools=["read"]))

	def gated_read(call_id):
		return MockModel(
			replies=[
				AssistantMessage(content=[ToolCall(id=call_id, name="read", arguments={"path": "a.txt"})])
			]
		)

	handle = await session.run("read", model=gated_read("c1"))
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.PAUSED
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.state is SessionState.PAUSED  # loading does not repair calls waiting for approval
	assert reloaded.log.latest_seq == session.log.latest_seq

	with pytest.raises(SessionConflict, match="paused for approval"):
		await session.rewind(1)
	with pytest.raises(SessionConflict, match="paused for approval"):
		await session.compact()
	assert "rewind" not in [r["type"] for r in session.log.read_since(0)]

	await session.set_model("mock/v2")
	assert session.state is SessionState.PAUSED  # the approval batch is untouched
	assert session.model == "mock/v2"

	handle = await session.resume({"c1": "Approve"}, model=gated_read("c2"))
	assert handle.task is not None
	await handle.task
	approval = session.transcript.pending_approval  # resumed, then paused on the next call
	assert approval is not None
	assert [call.id for call in approval.calls] == ["c2"]
	assert await session.cancel_pending() is True
	assert session.state is SessionState.IDLE

	first_call_seq = next(r["seq"] for r in session.log.read_since(0) if r["type"] == "assistant_message")
	with pytest.raises(RewindError, match="unanswered"):
		await session.rewind(first_call_seq)
	with pytest.raises(RewindError, match="does not exist"):
		await session.rewind(999)


def _reporting_config() -> SessionConfig:
	return SessionConfig(
		model="mock",
		callback_url="https://client.invalid/callback",
		notify_run_ended=True,
	)


async def _until(predicate, timeout=5.0):
	async with asyncio.timeout(timeout):
		while not predicate():
			await asyncio.sleep(0.01)


async def test_a_run_end_stays_marked_until_the_client_confirms_the_latest_one(tmp_path, monkeypatch):
	seen = []
	answers = []

	async def notify(config, session_id, terminal_seq, *, still_needed):
		seen.append((config.callback_url, session_id, terminal_seq, still_needed()))
		answers.append(asyncio.get_running_loop().create_future())
		return await answers[-1]

	monkeypatch.setattr("flow_harness.session.session.notify_run_ended", notify)
	session = SessionStore(str(tmp_path)).create(_reporting_config())
	ends = []
	for text in ("one", "two"):
		handle = await session.run(text, model=MockModel(replies=[AssistantMessage(content="ok")]))
		assert handle.task is not None
		await handle.task
		ends.append(session.log.latest_seq)
	await _until(lambda: len(answers) == 2)
	assert seen == [("https://client.invalid/callback", session.id, seq, True) for seq in ends]
	assert session.run_end_marker.exists()
	await session.set_model("mock/v2")  # a row after the end, but no new run

	answers[0].set_result(True)  # the first run's end, confirmed after the second run ended
	await asyncio.sleep(0.05)
	assert session.run_end_marker.exists()
	answers[1].set_result(True)
	await _until(lambda: not session.run_end_marker.exists())


async def test_startup_reports_the_run_ends_the_client_never_confirmed(tmp_path, monkeypatch):
	seen = []

	async def notify(config, session_id, terminal_seq, *, still_needed):
		seen.append((session_id, terminal_seq))
		return True

	monkeypatch.setattr("flow_harness.session.session.notify_run_ended", notify)
	store = SessionStore(str(tmp_path))
	ended = store.create(_reporting_config())
	ended.log.append(RunStarted(run_id="r1"))
	ended.log.append(UserMessage(content="go"))
	ended.log.append(AssistantMessage(content="done"))
	ended.log.append(RunEnded(reason="done"))
	cut_off = store.create(_reporting_config())
	cut_off.log.append(RunStarted(run_id="r1"))
	cut_off.log.append(UserMessage(content="go"))
	for session in (ended, cut_off):
		session.run_end_marker.touch()  # the daemon stopped before the client confirmed

	restarted = SessionStore(str(tmp_path))
	restarted.report_unconfirmed_run_ends()

	closed = restarted.get(cut_off.id).log.read_since(0)[-1]  # loading ended the cut-off run
	assert (closed["type"], closed["reason"]) == ("run_ended", "error")
	await _until(lambda: not ended.run_end_marker.exists() and not cut_off.run_end_marker.exists())
	assert sorted(seen) == sorted([(ended.id, 4), (cut_off.id, closed["seq"])])


def _callback_client(attempts: list, *, succeed_at: int | None):
	"""An httpx.AsyncClient stand-in that refuses posts before attempt `succeed_at` (None: always)."""

	class Client:
		def __init__(self, *args, **kwargs):
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			pass

		async def post(self, url, *, json, headers):
			attempts.append((url, json, headers))
			if succeed_at is None or len(attempts) < succeed_at:
				raise httpx.ConnectError("not yet", request=httpx.Request("POST", url))
			return httpx.Response(
				200,
				json={"message": {"synced_through": 7}},
				request=httpx.Request("POST", url),
			)

	return Client


async def test_terminal_notification_retries_until_confirmed_or_no_longer_needed(monkeypatch):
	monkeypatch.setattr("flow_harness.agent.client_tools._TERMINAL_RETRY_DELAYS", (0, 0, 0))
	attempts = []
	monkeypatch.setattr(
		"flow_harness.agent.client_tools.httpx.AsyncClient", _callback_client(attempts, succeed_at=8)
	)
	config = SessionConfig(
		callback_url="https://client.invalid/callback",
		callback_token="secret",
		notify_run_ended=True,
	)
	assert await notify_run_ended(config, "session-1", 7, still_needed=lambda: True) is True

	assert len(attempts) == 8  # past the quick retries, at the steady pace
	assert attempts[-1] == (
		"https://client.invalid/callback",
		{
			"callback_type": "run_ended",
			"session_id": "session-1",
			"terminal_seq": 7,
		},
		{"X-Harness-Token": "secret"},
	)

	attempts = []
	monkeypatch.setattr(
		"flow_harness.agent.client_tools.httpx.AsyncClient", _callback_client(attempts, succeed_at=None)
	)
	still_needed = iter([True, True, False])
	assert await notify_run_ended(config, "session-1", 7, still_needed=lambda: next(still_needed)) is False
	assert len(attempts) == 2


async def test_events_replay_then_stay_live_and_a_reload_starts_a_new_cursor(tmp_path):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	first = await session.run("one", model=MockModel(replies=[AssistantMessage(content="first")]))
	assert first.task is not None
	await first.task

	seen: list = []

	async def watch():
		async for event in session.events(since=0):
			seen.append(event)
			if event.type == "run_ended" and len([e for e in seen if e.type == "run_ended"]) == 2:
				return

	watcher = asyncio.create_task(watch())
	await asyncio.sleep(0)  # let the watcher replay history and subscribe
	second = await session.run("two", model=MockModel(replies=[AssistantMessage(content="second")]))
	assert second.task is not None
	await second.task
	await asyncio.wait_for(watcher, timeout=1)

	durable_seqs = [event.seq for event in seen if event.durable]
	assert durable_seqs == sorted(durable_seqs)
	assert len(durable_seqs) == len(set(durable_seqs))  # replay/live overlap deduplicated
	assert [event.content for event in seen if event.type == "user_message"] == ["one", "two"]

	before = session.event_snapshot()
	after = SessionStore(str(tmp_path)).get(session.id).event_snapshot()
	assert after["stream_id"] != before["stream_id"]
	assert after["revision"] == 0
	assert before["revision"] > 0
	assert after["entries"] == before["entries"]
	assert after["latest_seq"] == before["latest_seq"]


async def test_reconnecting_event_stream_replays_in_progress_deltas(tmp_path):
	class StreamingModel(MockModel):
		def __init__(self):
			super().__init__()
			self.prefix_sent = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			yield ThinkingDelta(thinking="think")
			yield ThinkingDelta(thinking="ing")
			yield TextDelta(text="pre")
			yield TextDelta(text="fix")
			self.prefix_sent.set()
			await self.release.wait()
			yield TextDelta(text=" suffix")
			yield AssistantMessage(content="prefix suffix")

	model = StreamingModel()
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	handle = await session.run("hi", model=model)
	await model.prefix_sent.wait()
	reconnect_cursor = session.log.latest_seq
	seen = []

	async def reconnect():
		async for event in session.events(since=reconnect_cursor):
			seen.append(event)
			if event.type == "run_ended":
				return

	watcher = asyncio.create_task(reconnect())
	await asyncio.sleep(0)  # let the reconnect subscribe
	model.release.set()
	assert handle.task is not None
	await handle.task
	await asyncio.wait_for(watcher, timeout=1)

	assert seen[0].type == "preview_replay_started"
	assert [event.thinking for event in seen if isinstance(event, ThinkingDelta)] == ["thinking"]
	assert [event.text for event in seen if isinstance(event, TextDelta)] == ["prefix", " suffix"]


async def test_slow_event_subscriber_is_dropped_and_can_reconnect(tmp_path, monkeypatch):
	monkeypatch.setattr("flow_harness.session.session._SUBSCRIBER_QUEUE_SIZE", 2)

	class BurstyModel(MockModel):
		def __init__(self):
			super().__init__()
			self.preview_sent = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			for text in ("a", "b", "c"):
				yield TextDelta(text=text)
			self.preview_sent.set()
			await self.release.wait()
			yield AssistantMessage(content="abc")

	model = BurstyModel()
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	stream = session.events()
	first_event = asyncio.create_task(anext(stream))
	await asyncio.sleep(0)
	handle = await session.run("hi", model=model)
	assert (await asyncio.wait_for(first_event, timeout=1)).type == "run_started"

	try:
		await model.preview_sent.wait()
		assert not session._subscribers
		with pytest.raises(StopAsyncIteration):
			await asyncio.wait_for(anext(stream), timeout=1)

		reconnected = session.events(since=1)
		try:
			replayed = [await asyncio.wait_for(anext(reconnected), timeout=1) for _ in range(3)]
			assert [event.type for event in replayed] == [
				"user_message",
				"preview_replay_started",
				"text_delta",
			]
			assert isinstance(replayed[-1], TextDelta)
			assert replayed[-1].text == "abc"
		finally:
			await reconnected.aclose()
	finally:
		model.release.set()
		assert handle.task is not None
		await handle.task
		await stream.aclose()


async def test_rewind_branches_and_the_next_run_follows_the_new_path(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	await session.set_model("mock/v2")
	rows_before = session.log.read_since(0)

	await session.rewind(1)  # branch from an entry mid-log, before the model change

	assert session.model == "mock"  # the change stayed behind on the abandoned branch
	handle = await session.run("B", model=MockModel(replies=[AssistantMessage(content="Y")]))
	assert handle.task is not None
	await handle.task
	texts = [getattr(m, "text", None) or m.content for m in session.transcript.messages]
	assert texts == ["B", "Y"]
	# nothing was deleted
	rows = session.log.read_since(0)
	assert rows[: len(rows_before)] == rows_before
	assert rows[len(rows_before)]["type"] == "rewind"
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert [getattr(m, "text", None) or m.content for m in reloaded.transcript.messages] == texts
	assert reloaded.model == "mock"
	assert reloaded.log.latest_seq == session.log.latest_seq  # load repaired nothing

	await session.rewind(0)  # to before everything

	assert session.transcript.messages == []
	handle = await session.run("C", model=MockModel(replies=[AssistantMessage(content="Z")]))
	assert handle.task is not None
	await handle.task
	assert [getattr(m, "text", None) or m.content for m in session.transcript.messages] == ["C", "Z"]
	# the new branch is a clean single run — no phantom run_started from the old one
	assert [r["type"] for r in active_path(session.log.read_since(0))] == [
		"run_started",
		"user_message",
		"assistant_message",
		"usage",
		"run_ended",
	]


async def test_rewinding_twice_lands_on_the_branch_the_first_marker_moved_to(tmp_path):
	"""A client that rewinds "to just before the last user message" aims at the row
	before its run_started — which, for the first run after a rewind, is the marker."""

	def target_before_last_user_message(session):
		rows = active_path(session.log.read_since(0))
		last_user = [r for r in rows if r["type"] == "user_message"][-1]
		return max(last_user["parent_seq"] - 1, 0)

	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	for text, reply in (("A", "X"), ("B", "Y")):
		handle = await session.run(text, model=MockModel(replies=[AssistantMessage(content=reply)]))
		assert handle.task is not None
		await handle.task

	await session.rewind(target_before_last_user_message(session))  # drops "B"
	handle = await session.run("C", model=MockModel(replies=[AssistantMessage(content="Z")]))
	assert handle.task is not None
	await handle.task
	await session.rewind(target_before_last_user_message(session))  # the marker's seq

	assert [getattr(m, "text", None) or m.content for m in session.transcript.messages] == ["A", "X"]
	handle = await session.run("D", model=MockModel(replies=[AssistantMessage(content="W")]))
	assert handle.task is not None
	await handle.task
	texts = [getattr(m, "text", None) or m.content for m in session.transcript.messages]
	assert texts == ["A", "X", "D", "W"]
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert [getattr(m, "text", None) or m.content for m in reloaded.transcript.messages] == texts


async def test_compact_writes_a_durable_summary_and_refuses_runs_meanwhile(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	rows_before = session.log.read_since(0)

	model = _Blocking(replies=[AssistantMessage(content="the summary")])
	handle = await session.compact("keep the goal", model=model)
	assert handle.status == "started"
	await model.started.wait()
	with pytest.raises(SessionConflict, match="compaction is in progress"):
		await session.run("during compaction", model=MockModel())
	assert not session._steering_queue  # nothing was queued for a later run to misplace
	model.release.set()
	assert handle.task is not None
	await handle.task

	assert session.state is SessionState.IDLE
	assert [m.content for m in session.transcript.messages] == ["Previous conversation summary:\nthe summary"]
	# nothing was deleted: the replaced rows are still on the path, before the new rows
	rows = session.log.read_since(0)
	assert rows[: len(rows_before)] == rows_before
	tail_types = [r["type"] for r in rows[len(rows_before) :]]
	# the summarizer's own call is durable too, marked so clients spend it without
	# reading its prompt as the conversation's new size
	assert tail_types == ["run_started", "compaction", "usage", "run_ended"]
	assert rows[-3]["reason"] == "manual"
	assert rows[-2]["standalone"] is True and rows[-2]["input_tokens"] > 0
	assert session.transcript.context_tokens is None
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert [m.model_dump() for m in reloaded.transcript.messages] == [
		m.model_dump() for m in session.transcript.messages
	]
	assert reloaded.log.latest_seq == session.log.latest_seq  # load repaired nothing

	handle = await session.run("after", model=MockModel(replies=[AssistantMessage(content="Y")]))
	assert handle.task is not None
	await handle.task
	texts = [getattr(m, "text", None) or m.content for m in session.transcript.messages]
	assert texts == ["Previous conversation summary:\nthe summary", "after", "Y"]


async def test_failed_or_aborted_compaction_settles_as_a_closed_run(tmp_path):
	store = SessionStore(str(tmp_path))
	events: list[dict] = []
	store.event_sink = lambda _sid, ev: events.append(ev)
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	messages_before = [m.model_dump() for m in session.transcript.messages]

	failing = MockModel(replies=[AssistantMessage(stop_reason="error", error_message="no summary")])
	handle = await session.compact(model=failing)
	assert handle.task is not None
	await handle.task

	assert session.state is SessionState.IDLE
	ended = [e for e in events if e["type"] == "compaction_ended"][-1]
	assert "no summary" in ended["error_message"]
	errors = [e for e in events if e["type"] == "run_error"]
	assert errors and "no summary" in errors[-1]["message"]
	assert [e["reason"] for e in events if e["type"] == "run_ended"][-1] == "error"
	assert [m.model_dump() for m in session.transcript.messages] == messages_before
	# A failed summary may still have used tokens; its report survives the failure.
	usage = [e for e in session.log.read_since(0) if e["type"] == "usage"][-1]
	assert usage["standalone"] is True and usage["input_tokens"] > 0

	rows_before = session.log.read_since(0)
	model = _Blocking()
	compacting = await session.compact(model=model)
	await model.started.wait()
	assert session.abort() is True
	assert compacting.task is not None
	await compacting.task

	assert session.state is SessionState.IDLE
	assert [e["type"] for e in events if e["type"].startswith("compaction")][-2:] == [
		"compaction_started",
		"compaction_ended",
	]
	ended = [e for e in events if e["type"] == "compaction_ended"][-1]
	assert ended["error_message"] == "aborted"
	# no compaction row, no fabricated assistant turn — just the aborted operation
	tail = session.log.read_since(0)[len(rows_before) :]
	assert [r["type"] for r in tail] == ["run_started", "run_ended"]
	assert tail[-1]["reason"] == "aborted"
	assert [m.model_dump() for m in session.transcript.messages] == messages_before
