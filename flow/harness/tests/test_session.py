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


def test_save_meta_persists_config_changes(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.config = session.config.model_copy(update={"model": "codex/gpt-test"})
	store.save_meta(session)

	assert SessionStore(str(tmp_path)).get(session.id).config.model == "codex/gpt-test"


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
