from flow_server.events import AssistantMessage, ToolCall, ToolResult, UserMessage
from flow_server.session.log import SessionLog
from flow_server.session.store import SessionConfig, SessionStore, _rebuild_messages


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
	log.append(AssistantMessage(text="", tool_calls=[call]))
	log.append(ToolResult(tool_call_id="c1", name="bash", content="file.txt"))

	msgs = _rebuild_messages(log)
	assert msgs[0] == {"role": "user", "content": "do it"}
	assert msgs[1]["role"] == "assistant"
	assert msgs[1]["tool_calls"][0]["function"]["name"] == "bash"
	assert msgs[2] == {"role": "tool", "tool_call_id": "c1", "content": "file.txt"}


def test_store_create_and_reload(tmp_path):
	store = SessionStore(str(tmp_path))
	session = store.create(SessionConfig(model="mock"))
	session.publish(UserMessage(content="remember me"))

	fresh = SessionStore(str(tmp_path))  # cold store, only disk
	reloaded = fresh.get(session.id)
	assert reloaded.config.model == "mock"
	assert reloaded.messages[0]["content"] == "remember me"
