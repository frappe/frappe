from flow_server.agent import HookDecision, resume, run
from flow_server.events import AssistantMessage, ToolCall
from flow_server.model.mock import MockModel
from flow_server.session.store import SessionConfig, SessionStore


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path), **cfg))
	return session, events


def _of(events, t):
	return [e for e in events if e["type"] == t]


def _read_call(cid="c1", path="a.txt"):
	return AssistantMessage(tool_calls=[ToolCall(id=cid, name="read_file", args={"path": path})])


async def test_full_turn_no_tools(tmp_path):
	session, events = _session(tmp_path)
	await run(session, "hi", model=MockModel(replies=[AssistantMessage(text="hello there")]))
	types = [e["type"] for e in events]
	assert "run_started" in types and "user_message" in types
	assert _of(events, "assistant_message")[0]["text"] == "hello there"
	assert _of(events, "run_ended")[0]["reason"] == "done"
	assert session.messages[0] == {"role": "user", "content": "hi"}


async def test_tool_call_runs_and_completes(tmp_path):
	(tmp_path / "a.txt").write_text("FILE-A")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(text="done")])
	await run(session, "read it", model=mock)
	tr = _of(events, "tool_result")
	assert len(tr) == 1
	assert tr[0]["content"] == "FILE-A"
	assert tr[0]["is_error"] is False
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_before_hook_rewrites_args(tmp_path):
	(tmp_path / "a.txt").write_text("AAA")
	(tmp_path / "b.txt").write_text("BBB")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(path="a.txt"), AssistantMessage(text="ok")])

	def before(tc, ctx):
		return HookDecision(args={"path": "b.txt"}) if tc.name == "read_file" else None

	await run(session, "read", model=mock, before_tool_call=before)
	assert _of(events, "tool_result")[0]["content"] == "BBB"  # hook redirected the read


async def test_before_hook_blocks(tmp_path):
	(tmp_path / "a.txt").write_text("AAA")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(text="ok")])

	def before(tc, ctx):
		return HookDecision(result="[blocked by policy]", is_error=True)

	await run(session, "read", model=mock, before_tool_call=before)
	tr = _of(events, "tool_result")[0]
	assert tr["content"] == "[blocked by policy]"
	assert tr["is_error"] is True


async def test_after_hook_rewrites_result(tmp_path):
	(tmp_path / "a.txt").write_text("sensitive-token-123")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(text="ok")])

	def after(tc, result):
		return "[redacted]" if "sensitive" in result.content else None

	await run(session, "read", model=mock, after_tool_call=after)
	assert _of(events, "tool_result")[0]["content"] == "[redacted]"


async def test_pause_and_resume(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(text="all done")])

	await run(session, "read", model=mock)
	approvals = _of(events, "approval_required")
	assert len(approvals) == 1
	assert approvals[0]["calls"][0]["id"] == "c1"
	assert _of(events, "run_ended")[0]["reason"] == "paused"
	assert _of(events, "tool_result") == []  # gated tool did not run

	await resume(session, {"c1": "Approve"}, model=mock)
	assert _of(events, "tool_result")[0]["content"] == "SECRET"
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_resume_deny_stops_run(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(text="unreached")])

	await run(session, "read", model=mock)
	await resume(session, {"c1": "Deny"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is True
	assert "denied" in tr["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert mock._turn == 1  # the model was NOT called again after denial


async def test_non_streaming_run(tmp_path):
	session, events = _session(tmp_path, stream=False)
	await run(session, "hi", model=MockModel(replies=[AssistantMessage(text="hi there friend")]))
	assert _of(events, "text_delta") == []  # no live deltas in non-streaming mode
	assert _of(events, "assistant_message")[0]["text"] == "hi there friend"
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_max_turns_cap(tmp_path):
	(tmp_path / "a.txt").write_text("x")
	session, events = _session(tmp_path, max_turns=2)
	# model keeps calling a tool every turn; the cap must stop it
	mock = MockModel(replies=[_read_call("c1"), _read_call("c2"), _read_call("c3")])
	await run(session, "loop", model=mock)
	assert _of(events, "run_ended")[0]["reason"] == "max_turns"
	assert len(_of(events, "tool_result")) == 2
