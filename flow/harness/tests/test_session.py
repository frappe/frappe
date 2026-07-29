import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from flow_server.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	TextContent,
	TextDelta,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_server.session.log import SessionLog, SessionLogError
from flow_server.session.store import (
	SessionConfig,
	SessionState,
	SessionStore,
	_rebuild_messages,
	interrupted_tool_repairs,
	pending_approval,
)


def test_session_config_includes_all_builtin_tools_by_default():
	assert SessionConfig().tools == ["bash", "read_file", "write", "edit", "grep"]


def test_log_seq_and_replay(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	assert log.append(UserMessage(content="hi")) == 1
	assert log.append(AssistantMessage(content="hello")) == 2
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


def test_log_rejects_partial_final_line_with_location(tmp_path):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="one"))
	with path.open("a") as file:
		file.write('{"type":"user_message"')

	with pytest.raises(SessionLogError, match=r"line 2 is not valid JSON"):
		SessionLog(str(path))


def test_log_rejects_invalid_event_with_location(tmp_path):
	path = tmp_path / "s.jsonl"
	path.write_text(json.dumps({"seq": 1, "type": "unknown"}) + "\n")

	with pytest.raises(SessionLogError, match=r"line 1 is not a valid event"):
		SessionLog(str(path))


def test_log_rejects_pre_release_assistant_shape(tmp_path):
	path = tmp_path / "s.jsonl"
	path.write_text(json.dumps({"seq": 1, "type": "assistant_message", "text": "old shape"}) + "\n")

	with pytest.raises(SessionLogError, match=r"line 1 is not a valid event"):
		SessionLog(str(path))


def test_append_rolls_back_a_partial_write(tmp_path, monkeypatch):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="first"))
	healthy = path.read_text()
	real_write, shortened = os.write, []

	def short_once(fd, data):
		if shortened:
			return real_write(fd, data)
		shortened.append(True)
		return real_write(fd, data[: len(data) // 2])  # e.g. the disk filled up

	monkeypatch.setattr(os, "write", short_once)
	with pytest.raises(OSError, match="short write"):
		log.append(UserMessage(content="second"))
	monkeypatch.undo()

	assert path.read_text() == healthy  # the partial line never survives
	log.append(UserMessage(content="third"))  # and the log is still appendable
	assert [row["seq"] for row in SessionLog(str(path)).read_since(0)] == [1, 2]


def test_log_error_locates_the_offending_row(tmp_path):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="one"))
	good_line_bytes = path.stat().st_size
	with path.open("a") as file:
		file.write('{"type":"user_message"\n')

	with pytest.raises(SessionLogError) as raised:
		SessionLog(str(path))

	assert raised.value.line == 2
	assert raised.value.offset == good_line_bytes  # byte where the bad row starts
	assert raised.value.reason == "is not valid JSON"


def test_log_rejects_non_monotonic_sequences(tmp_path):
	path = tmp_path / "s.jsonl"
	first = UserMessage(seq=2, content="one").model_dump_json()
	second = UserMessage(seq=1, content="two").model_dump_json()
	path.write_text(f"{first}\n{second}\n")

	with pytest.raises(SessionLogError, match=r"line 2 has non-monotonic seq 1 after 2"):
		SessionLog(str(path))


def test_log_serializes_concurrent_in_process_appends(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))

	def append(index: int) -> int:
		return log.append(UserMessage(content=str(index)))

	with ThreadPoolExecutor(max_workers=8) as executor:
		assigned = list(executor.map(append, range(100)))

	rows = log.read_since(0)
	assert sorted(assigned) == list(range(1, 101))
	assert [row["seq"] for row in rows] == list(range(1, 101))
	assert {row["content"] for row in rows} == {str(index) for index in range(100)}


def test_log_does_not_consume_sequence_when_write_fails(tmp_path, monkeypatch):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	real_write = os.write
	failed = False

	def fail_once(fd, data):
		nonlocal failed
		if not failed:
			failed = True
			raise OSError("disk unavailable")
		return real_write(fd, data)

	monkeypatch.setattr(os, "write", fail_once)
	event = UserMessage(content="one")

	with pytest.raises(OSError, match="disk unavailable"):
		log.append(event)

	assert event.seq is None
	assert log.latest_seq == 0
	assert log.append(event) == 1
	assert log.read_since(0)[0]["content"] == "one"


def test_log_rejects_direct_append_of_live_only_event(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))

	with pytest.raises(ValueError, match="live-only events cannot be appended"):
		log.append(TextDelta(text="transient"))

	assert log.latest_seq == 0


def test_rebuild_messages_roundtrip(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	log.append(UserMessage(content="do it"))
	reasoning = {"type": "reasoning", "id": "r1", "encrypted_content": "opaque"}
	call = ToolCall(id="c1", name="bash", arguments={"command": "ls"})
	log.append(
		AssistantMessage(
			content=[
				ThinkingContent(thinking="", thinking_signature=json.dumps(reasoning)),
				TextContent(text="working"),
				call,
			],
			api="openai-codex-responses",
			provider="codex",
			model="codex/gpt-test",
			response_id="resp_1",
			stop_reason="tool_use",
		)
	)
	log.append(ToolResult(tool_call_id="c1", name="bash", content="file.txt"))

	msgs = _rebuild_messages(log)
	assert isinstance(msgs[0], UserMessage)
	assert msgs[0].content == "do it"
	assert isinstance(msgs[1], AssistantMessage)
	assert [block.type for block in msgs[1].content] == ["thinking", "text", "tool_call"]
	assert msgs[1].tool_calls[0].name == "bash"
	assert msgs[1].response_id == "resp_1"
	assert isinstance(msgs[2], ToolResult)
	assert msgs[2].content == "file.txt"


def test_assistant_uses_flow_native_schema_names():
	message = AssistantMessage(
		content=[
			TextContent(text="answer", text_signature="msg_1"),
			ThinkingContent(thinking="plan", thinking_signature="opaque"),
			ToolCall(
				id="c1",
				name="bash",
				arguments={"command": "pwd"},
			),
		],
		api="responses",
		provider="provider",
		model="requested",
		response_model="actual",
		response_id="resp_1",
		stop_reason="tool_use",
	)

	payload = message.model_dump(exclude_none=True)

	assert payload["response_model"] == "actual"
	assert payload["response_id"] == "resp_1"
	assert payload["stop_reason"] == "tool_use"
	assert payload["content"][0]["text_signature"] == "msg_1"
	assert payload["content"][1]["thinking_signature"] == "opaque"
	assert message.thinking_text == "plan"


def test_store_create_and_reload(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.publish(UserMessage(content="remember me"))

	fresh = SessionStore(str(tmp_path))  # cold store, only disk
	reloaded = fresh.get(session.id)
	assert reloaded.config.model == "mock"
	assert reloaded.messages[0].content == "remember me"
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


def test_rebuild_keeps_the_first_result_and_drops_unmatched_ones(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	log.append(UserMessage(content="do it"))
	log.append(
		AssistantMessage(
			content=[ToolCall(id="c1", name="bash", arguments={})],
			stop_reason="tool_use",
		)
	)
	log.append(ToolResult(tool_call_id="c1", name="bash", content="first"))
	log.append(ToolResult(tool_call_id="c1", name="bash", content="second"))
	log.append(ToolResult(tool_call_id="unknown", name="bash", content="orphan"))

	msgs = _rebuild_messages(log)

	results = [m for m in msgs if isinstance(m, ToolResult)]
	assert [r.content for r in results] == ["first"]  # duplicate and orphan both excluded
	# every tool result the provider sees is preceded by the call it answers
	calls = {c.id for m in msgs if isinstance(m, AssistantMessage) for c in m.tool_calls}
	assert all(r.tool_call_id in calls for r in results)


def test_reload_durably_repairs_orphans_in_their_original_batch(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	call = ToolCall(id="c1", name="read_file", arguments={"path": "old.txt"})
	assistant = AssistantMessage(content=[call])
	session.publish(assistant)
	session.publish(RunEnded(reason="error"))
	session.publish(UserMessage(content="try something else"))
	session.publish(
		AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "new.txt"})])
	)
	session.publish(ToolResult(tool_call_id="c1", name="read_file", content="new result"))
	session.publish(RunEnded(reason="done"))
	before_repair = session.log.latest_seq

	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.log.latest_seq == before_repair + 1
	repair = reloaded.log.read_since(before_repair)[0]
	assert repair["tool_call_id"] == "c1"
	assert repair["is_error"] is True
	assert repair["details"]["transcript_repair"]["assistant_seq"] == assistant.seq
	assert [message.type for message in reloaded.messages] == [
		"assistant_message",
		"tool_result",
		"user_message",
		"assistant_message",
		"tool_result",
	]
	assert reloaded.messages[1].content == "Tool call interrupted before completion."
	assert reloaded.messages[-1].content == "new result"

	second_reload = SessionStore(str(tmp_path)).get(session.id)
	assert second_reload.log.latest_seq == reloaded.log.latest_seq


def test_reload_orders_actual_and_repaired_results_by_source_call(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.publish(
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read_file", arguments={"path": "first.txt"}),
				ToolCall(id="c2", name="read_file", arguments={"path": "second.txt"}),
			]
		)
	)
	session.publish(ToolResult(tool_call_id="c2", name="read_file", content="second result"))
	session.publish(RunEnded(reason="error"))

	reloaded = SessionStore(str(tmp_path)).get(session.id)

	assert [message.type for message in reloaded.messages] == [
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	assert [message.tool_call_id for message in reloaded.messages[1:]] == ["c1", "c2"]
	assert reloaded.messages[1].content == "Tool call interrupted before completion."
	assert reloaded.messages[2].content == "second result"


def test_reload_does_not_repair_calls_waiting_for_approval(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	call = ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})
	session.publish(AssistantMessage(content=[call]))
	session.publish(ApprovalRequired(calls=[PendingCall(id=call.id, name=call.name, args=call.args)]))
	session.publish(RunEnded(reason="paused"))
	latest_seq = session.log.latest_seq

	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.state is SessionState.PAUSED
	assert reloaded.log.latest_seq == latest_seq
	assert not any(row["type"] == "tool_result" for row in reloaded.log.read_since(0))


def test_interrupted_tool_repair_rejects_persisted_assistant_without_seq(tmp_path):
	path = tmp_path / "invalid.jsonl"
	log = SessionLog(str(path))
	path.write_text(
		AssistantMessage(
			content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})]
		).model_dump_json()
	)

	with pytest.raises(ValueError, match="missing a valid integer seq"):
		interrupted_tool_repairs(log)


def test_interrupted_tool_repair_rejects_unlinked_approval(tmp_path):
	log = SessionLog(str(tmp_path / "invalid.jsonl"))
	log.append(ApprovalRequired(calls=[PendingCall(id="c1", name="read_file", args={"path": "a.txt"})]))

	with pytest.raises(ValueError, match="approval event has no preceding assistant tool batch"):
		interrupted_tool_repairs(log)


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


async def test_session_operation_state_clears_if_state_rebuild_fails(tmp_path, monkeypatch):
	session = SessionStore(str(tmp_path)).create(SessionConfig(model="mock"))

	def fail_pending_approval(log):
		raise OSError("log unavailable")

	monkeypatch.setattr("flow_server.session.store.pending_approval", fail_pending_approval)

	async with session.operation_lock:
		task = session._start_operation(_complete())

	with pytest.raises(OSError, match="log unavailable"):
		await task
	assert session.state is SessionState.IDLE
	assert session.run_task is None


async def _complete() -> None:
	return
