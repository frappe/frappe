import json
import os

import pytest

from flow_server.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_server.session.log import SessionLog
from flow_server.session.store import (
	SessionConfig,
	SessionState,
	SessionStore,
	_rebuild_messages,
	pending_approval,
)


def test_session_config_includes_all_builtin_tools_by_default():
	assert SessionConfig().tools == ["bash", "read_file", "write", "edit", "grep"]


def test_log_seq_and_replay(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	assert log.append(UserMessage(content="hi")) == 1
	assert log.append(AssistantMessage(text="hello")) == 2
	assert log.latest_seq == 2

	all_rows = log.read_since(0)
	assert [r["seq"] for r in all_rows] == [1, 2]
	assert log.read_since(1)[0]["type"] == "assistant_message"
	assert log.read_since(2) == []


def test_log_survives_reopen(tmp_path):
	path = str(tmp_path / "s.jsonl")
	log = SessionLog(path)
	log.append(UserMessage(content="one"))
	log.append(UserMessage(content="two"))

	reopened = SessionLog(path)  # simulate a daemon restart
	assert reopened.latest_seq == 2
	assert reopened.append(UserMessage(content="three")) == 3


def test_rebuild_messages_roundtrip(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	log.append(UserMessage(content="do it"))
	call = ToolCall(id="c1", name="bash", args={"command": "ls"})
	log.append(
		AssistantMessage(
			text="",
			tool_calls=[call],
			provider_data={"codex_reasoning": [{"type": "reasoning", "id": "r1"}]},
		)
	)
	log.append(ToolResult(tool_call_id="c1", name="bash", content="file.txt"))

	msgs = _rebuild_messages(log)
	assert msgs[0] == {"role": "user", "content": "do it"}
	assert msgs[1]["role"] == "assistant"
	assert msgs[1]["tool_calls"][0]["function"]["name"] == "bash"
	assert msgs[1]["provider_data"]["codex_reasoning"][0]["id"] == "r1"
	assert msgs[2] == {"role": "tool", "tool_call_id": "c1", "content": "file.txt"}


def test_store_create_and_reload(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.publish(UserMessage(content="remember me"))

	fresh = SessionStore(str(tmp_path))  # cold store, only disk
	reloaded = fresh.get(session.id)
	assert reloaded.config.model == "mock"
	assert reloaded.messages[0]["content"] == "remember me"
	assert oct(os.stat(reloaded.log.path).st_mode & 0o777) == "0o600"


def test_store_creates_private_state_directories(tmp_path):
	data_dir = tmp_path / "state"
	store = SessionStore(str(data_dir))

	assert oct(os.stat(data_dir).st_mode & 0o777) == "0o700"
	assert oct(os.stat(store.sessions_dir).st_mode & 0o777) == "0o700"


def test_reload_discards_legacy_client_provider_auth(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	meta = tmp_path / "sessions" / f"{session.id}.meta.json"
	config = json.loads(meta.read_text())
	config["api_key"] = "legacy-secret"
	config["api_base"] = "https://attacker.test"
	meta.write_text(json.dumps(config))

	reloaded = SessionStore(str(tmp_path)).get(session.id)

	assert not hasattr(reloaded.config, "api_key")
	assert not hasattr(reloaded.config, "api_base")


def test_pending_approval_scopes_reused_tool_ids_to_latest_batch(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	call = PendingCall(id="c1", name="read_file", args={"path": "a.txt"})
	session.publish(ApprovalRequired(calls=[call]))
	session.publish(ToolResult(tool_call_id="c1", name="read_file", content="old"))
	session.publish(RunEnded(reason="done"))
	session.publish(ApprovalRequired(calls=[call]))
	session.publish(RunEnded(reason="paused"))

	approval = pending_approval(session.log)
	assert approval is not None
	assert approval.calls == (call,)


async def test_session_operation_state_clears_after_failure(tmp_path):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))

	async def fail() -> None:
		raise RuntimeError("boom")

	async with session.operation_lock:
		task = session._start_operation(fail())
		assert session.state is SessionState.RUNNING

	with pytest.raises(RuntimeError, match="boom"):
		await task
	assert session.state is SessionState.IDLE
	assert session.run_task is None
