"""The session layer: disk store, derived lifecycle state, crash repair at load,
and the live event surface."""

import asyncio
import json
import os

import pytest
from pydantic import ValidationError

from flow_server.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_server.model.credentials import CredentialStore
from flow_server.model.mock import MockModel
from flow_server.session.config import SessionConfig
from flow_server.session.session import SessionState
from flow_server.session.store import SessionStore


def test_session_config_includes_all_builtin_tools_by_default():
	assert SessionConfig().tools == ["bash", "read_file", "write", "edit", "grep"]


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
	(e.g. an injected api_key) fails loudly instead of being silently accepted."""
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	meta = tmp_path / "sessions" / f"{session.id}.meta.json"
	config = json.loads(meta.read_text())
	config["api_key"] = "injected-secret"
	meta.write_text(json.dumps(config))

	with pytest.raises(ValidationError):
		SessionStore(str(tmp_path)).get(session.id)


async def test_set_model_applies_to_later_runs_and_survives_restart(tmp_path, monkeypatch):
	resolved = []

	def spy(name, **kwargs):
		resolved.append(name)
		return MockModel()

	monkeypatch.setattr("flow_server.agent.loop.get_model", spy)
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


def test_reload_repairs_a_crashed_runs_open_calls(tmp_path):
	"""A daemon that died mid-turn left tool calls with no results. Loading the
	session closes them durably — once — so providers accept the transcript."""
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.log.append(UserMessage(content="go"))
	session.log.append(
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="read_file", arguments={"path": "b.txt"}),
			]
		)
	)
	session.log.append(ToolResult(tool_call_id="c2", name="read_file", content="second result"))
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
	call = ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})
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
	from flow_server.session.session import SessionConflict

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
	from flow_server.session.session import RewindError

	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path), confirm_tools=["read_file"]))
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
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
	from flow_server.session.session import ResumeError

	(tmp_path / "a.txt").write_text("x")
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(cwd=str(tmp_path), confirm_tools=["read_file"]))
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
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
	from flow_server.session.transcript import active_path

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


async def test_set_model_is_rejected_while_running(tmp_path):
	from flow_server.session.session import SessionConflict

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
		SessionConfig(model="mock", cwd=str(tmp_path), confirm_tools=["read_file"])
	)
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
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
