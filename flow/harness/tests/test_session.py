"""The session layer: disk store, derived lifecycle state, crash repair at load,
and the live event surface."""

import asyncio
import json
import os
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from flow_harness.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	TextDelta,
	ThinkingDelta,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.mock import MockModel
from flow_harness.session.config import SessionConfig
from flow_harness.session.session import SessionState
from flow_harness.session.store import SessionStore


def test_session_config_includes_all_builtin_tools_by_default():
	assert SessionConfig().tools == ["bash", "read", "write", "edit", "grep"]


def test_store_create_and_reload(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.log.append(UserMessage(content="remember me"))

	fresh = SessionStore(str(tmp_path))  # cold store, only disk
	reloaded = fresh.get(session.id)
	assert reloaded.config.model == "mock"
	assert reloaded.transcript.messages[0].content == "remember me"
	assert oct(os.stat(reloaded.log.path).st_mode & 0o777) == "0o600"


def test_store_creates_private_state_directories(tmp_path):
	data_dir = tmp_path / "state"
	store = SessionStore(str(data_dir))

	assert oct(os.stat(data_dir).st_mode & 0o777) == "0o700"
	assert oct(os.stat(store.sessions_dir).st_mode & 0o777) == "0o700"


def test_store_groups_session_artifacts_by_project(tmp_path):
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


def test_delete_removes_session_artifacts_and_prunes_only_empty_project_dirs(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	store = SessionStore(str(tmp_path / "state"))
	first = store.create(SessionConfig(cwd=str(project)))
	second = store.create(SessionConfig(cwd=str(project)))
	project_dir = Path(first.log.path).parent
	assert first.attachment_store is not None
	(Path(first.attachment_store.path) / "marker").write_text("bytes")

	store.delete(first.id)

	assert project_dir.is_dir()
	assert not Path(first.log.path).exists()
	assert not Path(first.attachment_store.path).exists()
	assert store.get(second.id) is second

	store.delete(second.id)
	assert not project_dir.exists()


def test_store_rejects_unsafe_session_ids(tmp_path):
	store = SessionStore(str(tmp_path))
	with pytest.raises(ValueError, match="invalid session_id"):
		store.create(SessionConfig(session_id="../../etc/x"))


def test_store_fences_cwd_to_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(allowed)])

	assert store.create(SessionConfig(cwd=str(allowed))).config.cwd == str(allowed)
	with pytest.raises(ValueError, match="not under an allowed root"):
		store.create(SessionConfig(cwd=str(tmp_path)))


def test_reload_rejects_tampered_meta(tmp_path):
	"""The config schema is closed: a meta file with fields the daemon never wrote
	fails loudly instead of being silently accepted."""
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	meta = Path(session.log.path).with_name(f"{session.id}.meta.json")
	config = json.loads(meta.read_text())
	config["injected_field"] = "injected-secret"
	meta.write_text(json.dumps(config))

	with pytest.raises(ValidationError):
		SessionStore(str(tmp_path)).get(session.id)


async def test_set_model_applies_to_later_runs_and_survives_restart(tmp_path, monkeypatch):
	resolved = []

	def spy(name, **kwargs):
		resolved.append(name)
		return MockModel()

	monkeypatch.setattr("flow_harness.agent.loop.get_model", spy)
	credentials = CredentialStore(str(tmp_path / "credentials.json"))  # keep auth offline
	store = SessionStore(str(tmp_path), credential_store=credentials)
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path)))

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


async def test_set_model_rejects_an_empty_name(tmp_path):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	with pytest.raises(ValueError, match="non-empty"):
		await session.set_model("")
	assert session.log.latest_seq == 0  # nothing became durable


def test_reload_repairs_a_crashed_runs_open_calls(tmp_path):
	"""A daemon that died mid-turn left tool calls with no results. Loading the
	session closes them durably — once — so providers accept the transcript."""
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.log.append(UserMessage(content="go"))
	session.log.append(
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="read", arguments={"path": "b.txt"}),
			]
		)
	)
	session.log.append(ToolResult(tool_call_id="c2", name="read", content="second result"))
	crashed_seq = session.log.latest_seq

	reloaded = SessionStore(str(tmp_path)).get(session.id)

	assert reloaded.log.latest_seq == crashed_seq + 1
	repair = reloaded.log.read_since(crashed_seq)[0]
	assert repair["tool_call_id"] == "c1"
	assert repair["is_error"] is True
	assert repair["details"]["repair"] == "interrupted"
	# position places the repair beside its call, in the order the calls were made
	assert [message.type for message in reloaded.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	assert [m.tool_call_id for m in reloaded.transcript.messages[2:]] == ["c1", "c2"]
	assert reloaded.transcript.messages[2].content == "Tool call interrupted before completion."
	assert reloaded.transcript.messages[3].content == "second result"

	second_reload = SessionStore(str(tmp_path)).get(session.id)
	assert second_reload.log.latest_seq == reloaded.log.latest_seq


def test_reload_does_not_repair_calls_waiting_for_approval(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	call = ToolCall(id="c1", name="read", arguments={"path": "a.txt"})
	session.log.append(AssistantMessage(content=[call]))
	session.log.append(ApprovalRequired(calls=[PendingCall(id=call.id, name=call.name, args=call.args)]))
	session.log.append(RunEnded(reason="paused"))
	latest_seq = session.log.latest_seq

	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.state is SessionState.PAUSED
	assert reloaded.log.latest_seq == latest_seq
	assert not any(row["type"] == "tool_result" for row in reloaded.log.read_since(0))


async def test_state_is_derived_from_task_and_transcript(tmp_path):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))
	assert session.state is SessionState.IDLE

	release = asyncio.Event()

	class GatedModel(MockModel):
		async def run(self, request):
			await release.wait()
			async for event in super().run(request):
				yield event

	handle = await session.run("hi", model=GatedModel(replies=[AssistantMessage(content="ok")]))
	assert session.state is SessionState.RUNNING
	release.set()
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.IDLE


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


async def test_events_replays_then_stays_live_without_duplicates(tmp_path):
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


async def test_live_cursor_changes_when_a_session_is_reloaded(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	handle = await session.run("hi", model=MockModel(replies=[AssistantMessage(content="hello")]))
	await handle.task
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
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	rows_before = session.log.read_since(0)

	await session.rewind(1)  # branch from an entry mid-log

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
	assert reloaded.log.latest_seq == session.log.latest_seq  # load repaired nothing


async def test_rewind_while_running_is_a_conflict(tmp_path):
	from flow_harness.session.session import SessionConflict

	class Blocking(MockModel):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await self.release.wait()
			yield AssistantMessage(content="done")

	model = Blocking()
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("go", model=model)
	await model.started.wait()

	with pytest.raises(SessionConflict):
		await session.rewind(1)

	model.release.set()
	assert handle.task is not None
	await handle.task


async def test_rewind_rejects_targets_that_leave_calls_open(tmp_path):
	from flow_harness.session.session import RewindError

	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path), confirm_tools=["read"]))
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])]
	)
	handle = await session.run("read", model=model)
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.PAUSED
	assistant_seq = next(r["seq"] for r in session.log.read_since(0) if r["type"] == "assistant_message")

	with pytest.raises(RewindError, match="unanswered"):
		await session.rewind(assistant_seq)
	with pytest.raises(RewindError, match="does not exist"):
		await session.rewind(999)


async def test_rewind_while_paused_abandons_the_approval_batch(tmp_path):
	from flow_harness.session.session import ResumeError

	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path), confirm_tools=["read"]))
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])]
	)
	handle = await session.run("read", model=model)
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.PAUSED

	await session.rewind(1)

	assert session.state is SessionState.IDLE
	with pytest.raises(ResumeError):  # the batch is on the dead branch
		await session.resume({"c1": "Approve"})
	# a reload does not repair the dead branch
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.log.latest_seq == session.log.latest_seq
	assert reloaded.state is SessionState.IDLE


async def test_rewind_to_zero_replaces_the_first_run(tmp_path):
	from flow_harness.session.transcript import active_path

	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task

	await session.rewind(0)

	assert session.transcript.messages == []
	handle = await session.run("B", model=MockModel(replies=[AssistantMessage(content="Y")]))
	assert handle.task is not None
	await handle.task
	assert [getattr(m, "text", None) or m.content for m in session.transcript.messages] == ["B", "Y"]
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
	from flow_harness.session.transcript import active_path

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


async def test_set_model_is_rejected_while_running(tmp_path):
	from flow_harness.session.session import SessionConflict

	class Blocking(MockModel):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await self.release.wait()
			yield AssistantMessage(content="done")

	model = Blocking()
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock", cwd=str(tmp_path)))
	handle = await session.run("go", model=model)
	await model.started.wait()

	with pytest.raises(SessionConflict):
		await session.set_model("mock/v2")

	model.release.set()
	assert handle.task is not None
	await handle.task
	assert session.model == "mock"


async def test_rewind_to_before_a_model_change_restores_the_old_selection(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	branch_point = session.log.latest_seq

	await session.set_model("mock/v2")
	assert session.model == "mock/v2"

	await session.rewind(branch_point)

	assert session.model == "mock"  # the change stayed behind on the abandoned branch
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.model == "mock"


async def test_set_model_while_paused_keeps_the_pause(tmp_path):
	(tmp_path / "a.txt").write_text("x")
	session = SessionStore(str(tmp_path)).create(
		SessionConfig(model="mock", cwd=str(tmp_path), confirm_tools=["read"])
	)
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])]
	)
	handle = await session.run("read", model=model)
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.PAUSED

	await session.set_model("mock/v2")

	assert session.state is SessionState.PAUSED  # the approval batch is untouched
	assert session.model == "mock/v2"
	handle = await session.resume(
		{"c1": "Approve"}, model=MockModel(replies=[AssistantMessage(content="done")])
	)
	assert handle.task is not None
	await handle.task
	assert session.state is SessionState.IDLE


async def test_compact_writes_a_durable_summary_and_survives_reload(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	rows_before = session.log.read_since(0)

	handle = await session.compact(
		"keep the goal", model=MockModel(replies=[AssistantMessage(content="the summary")])
	)
	assert handle.status == "started"
	assert handle.task is not None
	await handle.task

	assert session.state is SessionState.IDLE
	assert [m.content for m in session.transcript.messages] == ["Previous conversation summary:\nthe summary"]
	# nothing was deleted: the replaced rows are still on the path, before the new rows
	rows = session.log.read_since(0)
	assert rows[: len(rows_before)] == rows_before
	tail_types = [r["type"] for r in rows[len(rows_before) :]]
	assert tail_types == ["run_started", "compaction", "run_ended"]
	assert rows[-2]["reason"] == "manual"
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert [m.model_dump() for m in reloaded.transcript.messages] == [
		m.model_dump() for m in session.transcript.messages
	]
	assert reloaded.log.latest_seq == session.log.latest_seq  # load repaired nothing


async def test_compact_conflicts_while_running_paused_or_empty(tmp_path):
	from flow_harness.session.session import SessionConflict

	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))

	empty = store.create(SessionConfig(cwd=str(tmp_path)))
	with pytest.raises(SessionConflict, match="nothing to compact"):
		await empty.compact()

	class Blocking(MockModel):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await self.release.wait()
			yield AssistantMessage(content="done")

	model = Blocking()
	running = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await running.run("go", model=model)
	await model.started.wait()
	with pytest.raises(SessionConflict, match="already active"):
		await running.compact()
	model.release.set()
	assert handle.task is not None
	await handle.task

	paused = store.create(SessionConfig(cwd=str(tmp_path), confirm_tools=["read"]))
	gate = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])]
	)
	handle = await paused.run("read", model=gate)
	assert handle.task is not None
	await handle.task
	assert paused.state is SessionState.PAUSED
	with pytest.raises(SessionConflict, match="paused for approval"):
		await paused.compact()


async def test_compact_failure_settles_as_a_failed_run(tmp_path):
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


class _BlockingSummarizer(MockModel):
	"""Blocks inside the summarization call until released (or aborted)."""

	def __init__(self):
		super().__init__()
		self.started = asyncio.Event()
		self.release = asyncio.Event()

	async def run(self, request):
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="the summary")


async def test_run_during_manual_compact_is_a_conflict_not_steering(tmp_path):
	from flow_harness.session.session import SessionConflict

	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task

	model = _BlockingSummarizer()
	compacting = await session.compact(model=model)
	await model.started.wait()

	with pytest.raises(SessionConflict, match="compaction is in progress"):
		await session.run("during compaction", model=MockModel())
	assert not session._steering_queue  # nothing was queued for a later run to misplace

	model.release.set()
	assert compacting.task is not None
	await compacting.task

	handle = await session.run("after", model=MockModel(replies=[AssistantMessage(content="Y")]))
	assert handle.task is not None
	await handle.task
	texts = [getattr(m, "text", None) or m.content for m in session.transcript.messages]
	assert texts == ["Previous conversation summary:\nthe summary", "after", "Y"]


async def test_abort_during_manual_compact_closes_the_protocol_cleanly(tmp_path):
	store = SessionStore(str(tmp_path))
	events: list[dict] = []
	store.event_sink = lambda _sid, ev: events.append(ev)
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	handle = await session.run("A", model=MockModel(replies=[AssistantMessage(content="X")]))
	assert handle.task is not None
	await handle.task
	rows_before = session.log.read_since(0)
	messages_before = [m.model_dump() for m in session.transcript.messages]

	model = _BlockingSummarizer()
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
