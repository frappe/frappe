"""The agent loop driven through its session: turns, hooks, the approval gate,
steering, abort at every await point, and typed failure settlement."""

import asyncio

import pytest

from flow.agent.loop import HookDecision
from flow.events import AssistantMessage, ToolCall, Usage
from flow.model import Model, ModelRequest, ProviderError, run_with_retries
from flow.model.auth import ResolvedModelAuth
from flow.model.mock import MockModel
from flow.session.config import SessionConfig
from flow.session.session import ResumeError, SessionConflict
from flow.session.store import SessionStore
from flow.tools import BUILTIN_TOOLS, tool
from flow.tools.tool import ToolResult as RuntimeToolResult


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path), **cfg))
	return session, events


async def _run(session, message, **kwargs):
	handle = await session.run(message, **kwargs)
	assert handle.task is not None
	await handle.task
	return handle


async def _resume(session, answers, **kwargs):
	handle = await session.resume(answers, **kwargs)
	assert handle.task is not None
	await handle.task
	return handle


def _of(events, t):
	return [e for e in events if e["type"] == t]


def _read_call(cid="c1", path="a.txt"):
	return AssistantMessage(content=[ToolCall(id=cid, name="read_file", arguments={"path": path})])


async def test_full_turn_no_tools(tmp_path):
	session, events = _session(tmp_path)
	await _run(session, "hi", model=MockModel(replies=[AssistantMessage(content="hello there")]))
	types = [e["type"] for e in events]
	assert "run_started" in types and "user_message" in types
	assert _of(events, "assistant_message")[0]["content"][0]["text"] == "hello there"
	assert _of(events, "run_ended")[0]["reason"] == "done"
	assert session.transcript.messages[0].type == "user_message"
	assert session.transcript.messages[0].content == "hi"


async def test_custom_tool_display_template_reaches_the_model_request(tmp_path):
	@tool(display_template="Searching the web for {{ query }}")
	async def web_search(query: str, *, ctx) -> RuntimeToolResult:
		del ctx
		return RuntimeToolResult(content=query)

	class RecordingMock(MockModel):
		def __init__(self):
			super().__init__(replies=[AssistantMessage(content="done")])
			self.requests: list[ModelRequest] = []

		async def run(self, request):
			self.requests.append(request)
			async for event in super().run(request):
				yield event

	session, _ = _session(tmp_path)
	assert session.server_tools is not None
	session.server_tools[web_search.name] = web_search
	model = RecordingMock()

	await _run(session, "search", model=model)

	assert model.requests[0].tool_display_templates["web_search"] == ("Searching the web for {{ query }}")


async def test_tool_call_runs_and_completes(tmp_path):
	(tmp_path / "a.txt").write_text("FILE-A")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="done")])
	await _run(session, "read it", model=mock)
	tr = _of(events, "tool_result")
	assert len(tr) == 1
	assert tr[0]["content"] == "FILE-A"
	assert tr[0]["is_error"] is False
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_allowed_roots_propagate_to_path_tools(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	(tmp_path / "secret.txt").write_text("SECRET")
	events: list[dict] = []
	store = SessionStore(
		str(tmp_path / "data"),
		event_sink=lambda _sid, ev: events.append(ev),
		allowed_roots=[str(allowed)],
	)
	session = store.create(SessionConfig(cwd=str(allowed)))
	mock = MockModel(replies=[_read_call(path="../secret.txt"), AssistantMessage(content="done")])

	await _run(session, "read outside the project", model=mock)

	result = _of(events, "tool_result")[0]
	assert result["is_error"] is True
	assert "outside the configured allowed roots" in result["content"]
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_before_hook_rewrites_args(tmp_path):
	(tmp_path / "a.txt").write_text("AAA")
	(tmp_path / "b.txt").write_text("BBB")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(path="a.txt"), AssistantMessage(content="ok")])

	def before(tc, ctx):
		return HookDecision(args={"path": "b.txt"}) if tc.name == "read_file" else None

	await _run(session, "read", model=mock, before_tool_call=before)
	assert _of(events, "tool_result")[0]["content"] == "BBB"  # hook redirected the read


async def test_before_hook_blocks(tmp_path):
	(tmp_path / "a.txt").write_text("AAA")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="ok")])

	def before(tc, ctx):
		return HookDecision(result="[blocked by policy]", is_error=True)

	await _run(session, "read", model=mock, before_tool_call=before)
	tr = _of(events, "tool_result")[0]
	assert tr["content"] == "[blocked by policy]"
	assert tr["is_error"] is True


async def test_after_hook_rewrites_result(tmp_path):
	(tmp_path / "a.txt").write_text("sensitive-token-123")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="ok")])

	def after(tc, result):
		return "[redacted]" if "sensitive" in result.content else None

	await _run(session, "read", model=mock, after_tool_call=after)
	assert _of(events, "tool_result")[0]["content"] == "[redacted]"


async def test_pause_and_resume(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="all done")])

	await _run(session, "read", model=mock)
	approvals = _of(events, "approval_required")
	assert len(approvals) == 1
	assert approvals[0]["calls"][0]["id"] == "c1"
	assert _of(events, "run_ended")[0]["reason"] == "paused"
	assert _of(events, "tool_result") == []  # gated tool did not run

	await _resume(session, {"c1": "Approve"}, model=mock)
	assert _of(events, "tool_result")[0]["content"] == "SECRET"
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert len(_of(events, "run_started")) == 2  # the resumed run announces itself


async def test_resume_deny_stops_run(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="unreached")])

	await _run(session, "read", model=mock)
	await _resume(session, {"c1": "Deny"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is True
	assert "denied" in tr["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "denied"
	assert mock._turn == 1  # the model was NOT called again after denial


async def test_resume_redirect_feeds_the_model_the_users_feedback(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="adjusted")])

	await _run(session, "read", model=mock)
	await _resume(session, {"c1": "use the other file"}, model=mock)

	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is False
	assert "use the other file" in tr["content"]
	assert mock._turn == 2  # the model got a turn to adjust
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_resume_rejects_non_exact_answers_without_mutating_log(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", arguments={"path": "a.txt"}),
				]
			)
		]
	)
	await _run(session, "read", model=mock)
	approval_seq = _of(events, "approval_required")[0]["seq"]
	latest_seq = session.log.latest_seq

	with pytest.raises(ResumeError, match="missing answers for: c2"):
		await session.resume({"c1": "Approve"}, approval_seq=approval_seq, model=mock)
	with pytest.raises(ResumeError, match="stale"):
		await session.resume({"c1": "Approve", "c2": "Approve"}, approval_seq=approval_seq - 1, model=mock)

	assert session.log.latest_seq == latest_seq
	assert _of(events, "tool_result") == []


async def test_gating_a_client_tool_does_not_ungate_the_builtins(tmp_path):
	"""confirm_tools adds gates on top of each tool's default; naming one tool must
	not silently switch approval off for bash/write/edit."""
	session, events = _session(tmp_path, confirm_tools=["send_email"])
	mock = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="bash", arguments={"command": "pwd"})])]
	)

	await _run(session, "run it", model=mock)

	assert _of(events, "tool_result") == []  # bash stayed gated
	approval = _of(events, "approval_required")[0]
	assert [call["id"] for call in approval["calls"]] == ["c1"]
	assert _of(events, "run_ended")[0]["reason"] == "paused"


async def test_run_while_paused_is_a_conflict(tmp_path):
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	await _run(session, "read", model=MockModel(replies=[_read_call()]))
	assert _of(events, "run_ended")[0]["reason"] == "paused"

	with pytest.raises(SessionConflict, match="paused for approval"):
		await session.run("something else", model=MockModel())


async def test_cancel_pending_closes_the_batch_and_frees_the_session(tmp_path):
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	await _run(session, "read", model=MockModel(replies=[_read_call()]))
	assert session.state == "paused"

	assert await session.cancel_pending() is True

	assert session.state == "idle"
	assert session.transcript.pending_approval is None
	cancelled = _of(events, "tool_result")
	assert [r["tool_call_id"] for r in cancelled] == ["c1"]
	assert all("cancelled" in r["content"] and r["is_error"] for r in cancelled)

	# the session is usable again
	await _run(session, "hi", model=MockModel(replies=[AssistantMessage(content="fresh")]))
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert await session.cancel_pending() is False  # nothing pending anymore


async def test_steering_joins_the_active_run_as_a_new_turn(tmp_path):
	release = asyncio.Event()
	started = asyncio.Event()

	class WaitingModel(Model):
		name = "waiting"

		def __init__(self):
			self.turn = 0

		async def run(self, request: ModelRequest):
			self.turn += 1
			if self.turn == 1:
				started.set()
				await release.wait()
			yield AssistantMessage(content=f"reply-{self.turn}")
			yield Usage()

	session, events = _session(tmp_path)
	model = WaitingModel()
	first = await session.run("start", model=model)
	await started.wait()

	second = await session.run("and another thing", model=model)
	assert second.status == "steered"
	assert second.task is None

	release.set()
	assert first.task is not None
	await first.task

	assert [e["content"] for e in _of(events, "user_message")] == ["start", "and another thing"]
	assert [e["content"][0]["text"] for e in _of(events, "assistant_message")] == ["reply-1", "reply-2"]
	assert [e["reason"] for e in _of(events, "run_ended")] == ["done"]


async def test_non_streaming_run(tmp_path):
	session, events = _session(tmp_path, stream=False)
	await _run(session, "hi", model=MockModel(replies=[AssistantMessage(content="hi there friend")]))
	assert _of(events, "text_delta") == []  # no live deltas in non-streaming mode
	assert _of(events, "assistant_message")[0]["content"][0]["text"] == "hi there friend"
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_length_stop_is_not_reported_as_done(tmp_path):
	session, events = _session(tmp_path)
	reply = AssistantMessage(content="partial", stop_reason="length")

	await _run(session, "hi", model=MockModel(replies=[reply]))

	assert _of(events, "assistant_message")[0]["stop_reason"] == "length"
	assert _of(events, "run_ended")[0]["reason"] == "length"


async def test_truncated_turn_fails_its_tool_calls_without_running_them(tmp_path):
	session, events = _session(tmp_path)
	truncated = AssistantMessage(
		content=[
			ToolCall(id="c1", name="write", arguments={"path": "a.txt", "content": "x"}),
			ToolCall(id="c2", name="write", arguments={"path": "b.txt", "content": "y"}),
		],
		stop_reason="length",
	)
	mock = MockModel(replies=[truncated, AssistantMessage(content="retried")])

	await _run(session, "write them", model=mock)

	results = _of(events, "tool_result")
	assert [r["tool_call_id"] for r in results] == ["c1", "c2"]
	assert all(r["is_error"] and "truncated" in r["content"] for r in results)
	assert not (tmp_path / "a.txt").exists() and not (tmp_path / "b.txt").exists()
	# the model still gets a turn to re-issue the calls
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_max_turns_cap(tmp_path):
	(tmp_path / "a.txt").write_text("x")
	session, events = _session(tmp_path, max_turns=2)
	# model keeps calling a tool every turn; the cap must stop it
	mock = MockModel(replies=[_read_call("c1"), _read_call("c2"), _read_call("c3")])
	await _run(session, "loop", model=mock)
	assert _of(events, "run_ended")[0]["reason"] == "max_turns"
	assert len(_of(events, "tool_result")) == 2


async def test_setup_failure_emits_one_terminal_error(tmp_path, monkeypatch):
	session, events = _session(tmp_path)

	async def fail_auth(*args, **kwargs):
		raise RuntimeError("auth setup failed")

	monkeypatch.setattr("flow.agent.loop.resolve_model_auth", fail_auth)
	await _run(session, "hi")

	assert _of(events, "run_error")[0]["message"] == "RuntimeError: auth setup failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


async def test_run_wires_the_resolved_refresh_hook_into_the_model(tmp_path, monkeypatch):
	async def refresh(rejected_token):
		raise AssertionError("never called here")

	async def fake_resolve(*_args, **_kwargs):
		return ResolvedModelAuth(api_key="live", source="OAuth", provider_id="codex", refresh=refresh)

	captured = {}

	def fake_get_model(name, **kwargs):
		captured["name"] = name
		captured.update(kwargs)
		return MockModel(replies=[AssistantMessage(content="ok")])

	monkeypatch.setattr("flow.agent.loop.resolve_model_auth", fake_resolve)
	monkeypatch.setattr("flow.agent.loop.get_model", fake_get_model)
	session, events = _session(tmp_path, model="codex/test")

	await _run(session, "hello")

	assert captured["name"] == "codex/test"
	assert captured["api_key"] == "live"
	assert captured["refresh_auth"] is refresh
	assert [event["reason"] for event in _of(events, "run_ended")] == ["done"]


async def test_reasoning_effort_reaches_the_model_as_params(tmp_path, monkeypatch):
	captured = {}

	def fake_get_model(name, **kwargs):
		captured.update(kwargs)
		return MockModel(replies=[AssistantMessage(content="ok")])

	monkeypatch.setattr("flow.agent.loop.get_model", fake_get_model)
	session, _ = _session(tmp_path, reasoning_effort="high")

	await _run(session, "hello")

	assert captured["params"]["reasoning_effort"] == "high"


async def test_no_reasoning_effort_sends_no_params(tmp_path, monkeypatch):
	captured = {}

	def fake_get_model(name, **kwargs):
		captured.update(kwargs)
		return MockModel(replies=[AssistantMessage(content="ok")])

	monkeypatch.setattr("flow.agent.loop.get_model", fake_get_model)
	session, _ = _session(tmp_path)

	await _run(session, "hello")

	assert captured["params"] is None


async def test_hook_failure_repairs_all_unreturned_tool_calls(tmp_path):
	session, events = _session(tmp_path)
	mock = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", arguments={"path": "b.txt"}),
				]
			)
		]
	)

	def fail_before(tc, ctx):
		raise RuntimeError("hook failed")

	await _run(session, "read", model=mock, before_tool_call=fail_before)

	results = _of(events, "tool_result")
	assert [result["tool_call_id"] for result in results] == ["c1", "c2"]
	assert all(result["is_error"] for result in results)
	assert all(result["details"]["repair"] == "interrupted" for result in results)
	assert _of(events, "run_error")[0]["message"] == "RuntimeError: hook failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]
	assert [message.type for message in session.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	latest_seq = session.log.latest_seq
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.log.latest_seq == latest_seq  # settlement already closed the turn


async def test_model_stream_failure_repairs_persisted_assistant_calls(tmp_path, monkeypatch):
	session, events = _session(tmp_path)
	mock = MockModel()

	async def fail_after_assistant(request):
		yield _read_call()
		raise RuntimeError("stream failed")

	monkeypatch.setattr(mock, "run", fail_after_assistant)
	await _run(session, "read", model=mock)

	assert [result["tool_call_id"] for result in _of(events, "tool_result")] == ["c1"]
	assert _of(events, "run_error")[0]["message"] == "RuntimeError: stream failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]
	assert [message.type for message in session.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
	]


async def test_model_stream_without_assistant_emits_terminal_error(tmp_path, monkeypatch):
	session, events = _session(tmp_path)
	mock = MockModel()

	async def empty_stream(request):
		if False:
			yield

	monkeypatch.setattr(mock, "run", empty_stream)
	await _run(session, "hi", model=mock)

	assert _of(events, "run_error")[0]["message"] == (
		"RuntimeError: model stream ended without an assistant message"
	)
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


class _CancellationBlockingModel(Model):
	name = "cancellation-blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.closed = asyncio.Event()
		self.requests: list[ModelRequest] = []
		self.attempts = 0

	async def run(self, request: ModelRequest):
		self.requests.append(request)
		self.attempts += 1
		self.started.set()
		try:
			await asyncio.Event().wait()
		finally:
			self.closed.set()
		if False:
			yield


async def test_abort_during_model_stream_closes_stream_and_emits_aborted_turn(tmp_path):
	session, events = _session(tmp_path)
	model = _CancellationBlockingModel()

	handle = await session.run("wait", model=model)
	await model.started.wait()
	assert session.abort() is True
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)

	assert model.requests[0].cancellation is session.abort_signal
	assert model.closed.is_set()
	assert model.attempts == 1
	assert [event["stop_reason"] for event in _of(events, "assistant_message")] == ["aborted"]
	assert [event["reason"] for event in _of(events, "run_ended")] == ["aborted"]
	assert _of(events, "run_error") == []


async def test_aborted_terminal_with_tool_calls_closes_them_durably(tmp_path):
	"""An aborted turn can still carry tool calls; the loop must answer them."""
	session, events = _session(tmp_path)
	model = MockModel(
		replies=[
			AssistantMessage(
				content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})],
				stop_reason="aborted",
			)
		]
	)

	await _run(session, "go", model=model)

	results = _of(events, "tool_result")
	assert [r["tool_call_id"] for r in results] == ["c1"]
	assert results[0]["is_error"] is True
	assert "aborted" in results[0]["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"
	assert session.transcript.missing_results() == ()  # a reload would repair nothing


async def test_abort_cancels_blocked_before_hook_before_tool_starts(tmp_path):
	(tmp_path / "a.txt").write_text("secret")
	session, events = _session(tmp_path)
	model = MockModel(replies=[_read_call()])
	hook_started = asyncio.Event()
	hook_cancelled = asyncio.Event()

	async def before(tc, ctx):
		hook_started.set()
		try:
			await asyncio.Event().wait()
		finally:
			hook_cancelled.set()

	handle = await session.run("read", model=model, before_tool_call=before)
	await hook_started.wait()
	session.abort()
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)

	assert hook_cancelled.is_set()
	results = _of(events, "tool_result")
	assert len(results) == 1
	assert results[0]["details"]["repair"] == "interrupted"
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


async def test_abort_cancels_blocked_after_hook(tmp_path):
	(tmp_path / "a.txt").write_text("secret")
	session, events = _session(tmp_path)
	model = MockModel(replies=[_read_call()])
	hook_started = asyncio.Event()
	hook_cancelled = asyncio.Event()

	async def after(tc, result):
		hook_started.set()
		try:
			await asyncio.Event().wait()
		finally:
			hook_cancelled.set()

	handle = await session.run("read", model=model, after_tool_call=after)
	await hook_started.wait()
	session.abort()
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)

	assert hook_cancelled.is_set()
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


async def test_abort_between_tool_calls_prevents_later_tool_from_starting(tmp_path, monkeypatch):
	started: list[str] = []

	@tool
	async def first(*, ctx):
		started.append("first")
		ctx.abort.set()
		return RuntimeToolResult(content="first finished")

	@tool
	async def second(*, ctx):
		started.append("second")
		return RuntimeToolResult(content="second finished")

	monkeypatch.setitem(BUILTIN_TOOLS, "first", first)
	monkeypatch.setitem(BUILTIN_TOOLS, "second", second)
	session, events = _session(tmp_path, tools=["first", "second"], auto_approve=True)
	model = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="first", arguments={}),
					ToolCall(id="c2", name="second", arguments={}),
				]
			)
		]
	)

	await _run(session, "go", model=model)

	assert started == ["first"]
	assert [event["tool_call_id"] for event in _of(events, "tool_result")] == ["c1", "c2"]
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


async def test_client_tool_round_trips_the_callback_and_unwraps_the_frappe_envelope(tmp_path, monkeypatch):
	seen = {}

	class RecordingClient:
		def __init__(self, *args, **kwargs):
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			return None

		async def post(self, url, *, json, headers):
			seen.update(url=url, payload=json, headers=headers)

			class Response:
				def raise_for_status(self):
					pass

				def json(self):
					return {"message": {"content": "42 unread emails", "is_error": False}}

			return Response()

	monkeypatch.setattr("flow.agent.client_tools.httpx.AsyncClient", RecordingClient)
	session, events = _session(
		tmp_path,
		tools=[],
		client_tools=[
			{
				"type": "function",
				"function": {
					"name": "check_mail",
					"description": "count mail",
					"parameters": {"type": "object", "properties": {}},
				},
			}
		],
		callback_url="https://client.invalid/tools",
		callback_token="shared-secret",
		user_context={"user": "alice"},
		auto_approve=True,
	)
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="client-1", name="check_mail", arguments={})]),
			AssistantMessage(content="done"),
		]
	)

	await _run(session, "check my mail", model=model)

	assert seen["url"] == "https://client.invalid/tools"
	assert seen["headers"]["X-Harness-Token"] == "shared-secret"
	assert seen["payload"] == {
		"session_id": session.id,
		"tool": "check_mail",
		"args": {},
		"user_context": {"user": "alice"},
		"mode": "execute",
	}
	results = _of(events, "tool_result")
	assert [r["content"] for r in results] == ["42 unread emails"]  # envelope unwrapped
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_abort_cancels_client_callback_request(tmp_path, monkeypatch):
	callback_started = asyncio.Event()
	callback_cancelled = asyncio.Event()

	class BlockingClient:
		def __init__(self, *args, **kwargs):
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			return None

		async def post(self, *args, **kwargs):
			callback_started.set()
			try:
				await asyncio.Event().wait()
			finally:
				callback_cancelled.set()

	monkeypatch.setattr("flow.agent.client_tools.httpx.AsyncClient", BlockingClient)
	session, events = _session(
		tmp_path,
		tools=[],
		client_tools=[
			{
				"type": "function",
				"function": {
					"name": "client_wait",
					"description": "wait",
					"parameters": {"type": "object", "properties": {}},
				},
			}
		],
		callback_url="https://client.invalid/tools",
		auto_approve=True,
	)
	model = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="client-1", name="client_wait", arguments={})])]
	)

	handle = await session.run("call client", model=model)
	await callback_started.wait()
	session.abort()
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)

	assert callback_cancelled.is_set()
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


class _FailingModel(Model):
	"""A bare adapter whose failures reach the loop untreated — no retry envelope."""

	name = "failing"
	provider = "test"
	api = "test"
	model = "test/failing"

	def __init__(self, error: ProviderError):
		self.error = error
		self.attempts = 0

	async def run(self, request: ModelRequest):
		self.attempts += 1
		raise self.error
		if False:
			yield


async def test_provider_failure_escaping_the_model_fails_the_run_typed(tmp_path):
	session, events = _session(tmp_path)
	model = _FailingModel(
		ProviderError(
			kind="invalid_request",
			retryable=False,
			status_code=400,
			provider="test",
			detail="bad input",
		)
	)

	await _run(session, "try", model=model)

	assert model.attempts == 1
	error = _of(events, "run_error")[0]
	assert (error["kind"], error["retryable"], error["status_code"]) == ("invalid_request", False, 400)
	assert error["detail"] == "bad input"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


async def test_context_overflow_ends_the_run_typed(tmp_path):
	session, events = _session(tmp_path)
	model = _FailingModel(
		ProviderError(
			kind="context_overflow",
			retryable=False,
			status_code=400,
			provider="test",
			detail="context_length_exceeded",
		)
	)

	await _run(session, "too much", model=model)

	assert _of(events, "run_error")[0]["kind"] == "context_overflow"
	assert _of(events, "run_error")[0]["detail"] == "context_length_exceeded"
	assert _of(events, "run_ended")[0]["reason"] == "error"


BIG = "x" * 100_000  # ~25k estimated tokens: past any test threshold, over the kept tail


class _OverflowThenRecoverModel(Model):
	"""Call 1 overflows; call 2 serves the summarizer; call 3 answers."""

	name = "overflow-recover"

	def __init__(self):
		self.calls = 0

	async def run(self, request: ModelRequest):
		self.calls += 1
		if self.calls == 1:
			raise ProviderError(
				kind="context_overflow",
				retryable=False,
				status_code=400,
				provider="test",
				detail="prompt is too long",
			)
		if self.calls == 2:
			yield AssistantMessage(content="## Goal\noverflow summary")
		else:
			yield AssistantMessage(content="recovered")
		yield Usage(input_tokens=10, output_tokens=5)


async def test_threshold_compaction_folds_before_the_next_model_call(tmp_path):
	session, events = _session(tmp_path, compact_threshold_tokens=100)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first answer")]))
	assert _of(events, "compaction") == []  # a single turn has nothing old enough to replace

	mock = MockModel(
		replies=[
			AssistantMessage(content="## Goal\ncompacted summary"),  # consumed by the summarizer
			AssistantMessage(content="final answer"),
		]
	)
	await _run(session, "continue", model=mock)

	assert mock._turn == 2
	row = _of(events, "compaction")[0]
	assert row["reason"] == "threshold"
	final = _of(events, "assistant_message")[-1]
	assert final["content"][0]["text"] == "final answer"
	assert row["seq"] < final["seq"]  # folded before the turn's model call
	# the summarizer's stream never leaks to subscribers
	deltas = "".join(e["text"] for e in _of(events, "text_delta"))
	assert "compacted summary" not in deltas
	msgs = session.transcript.messages
	assert [m.type for m in msgs] == ["user_message", "user_message", "assistant_message"]
	assert msgs[0].content.startswith("Previous conversation summary:")
	assert "compacted summary" in msgs[0].content
	assert msgs[1].content == "continue"
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	# a reload folds identically
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert [m.model_dump() for m in reloaded.transcript.messages] == [m.model_dump() for m in msgs]


async def test_threshold_compaction_failure_keeps_the_turn(tmp_path):
	session, events = _session(tmp_path, compact_threshold_tokens=100)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first answer")]))

	mock = MockModel(
		replies=[
			AssistantMessage(stop_reason="error", error_message="summarizer down"),
			AssistantMessage(content="still answered"),
		]
	)
	await _run(session, "continue", model=mock)

	assert _of(events, "compaction") == []
	ended = _of(events, "compaction_ended")[-1]
	assert "summarizer down" in ended["error_message"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert len(session.transcript.messages) == 4  # nothing was folded
	assert session.transcript.messages[-1].text == "still answered"


async def test_overflow_compacts_once_and_retries_the_turn(tmp_path):
	session, events = _session(tmp_path)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first answer")]))

	model = _OverflowThenRecoverModel()
	await _run(session, "continue", model=model)

	assert model.calls == 3
	row = _of(events, "compaction")[0]
	assert row["reason"] == "overflow"
	assert _of(events, "run_error") == []
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	msgs = session.transcript.messages
	assert msgs[0].content.startswith("Previous conversation summary:")
	assert msgs[-1].text == "recovered"


async def test_a_second_overflow_in_the_same_run_fails_typed(tmp_path):
	class AlwaysOverflow(Model):
		name = "always-overflow"

		def __init__(self):
			self.calls = 0

		async def run(self, request: ModelRequest):
			self.calls += 1
			if self.calls == 2:  # only the summarizer call succeeds
				yield AssistantMessage(content="summary")
				yield Usage(input_tokens=1, output_tokens=1)
				return
			raise ProviderError(
				kind="context_overflow",
				retryable=False,
				status_code=400,
				provider="test",
				detail="still too long",
			)

	session, events = _session(tmp_path)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first")]))

	model = AlwaysOverflow()
	await _run(session, "continue", model=model)

	assert model.calls == 3  # original, summarizer, failed retry — no second recovery
	assert len(_of(events, "compaction")) == 1  # the recovery itself is durable
	assert _of(events, "run_error")[-1]["kind"] == "context_overflow"
	assert _of(events, "run_ended")[-1]["reason"] == "error"


async def test_auto_compact_disabled_turns_both_paths_off(tmp_path):
	session, events = _session(tmp_path, auto_compact=False, compact_threshold_tokens=10)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="one")]))
	await _run(session, "again", model=MockModel(replies=[AssistantMessage(content="two")]))
	assert _of(events, "compaction_started") == []

	failing = _FailingModel(
		ProviderError(kind="context_overflow", retryable=False, status_code=400, provider="test", detail="x")
	)
	await _run(session, "boom", model=failing)

	assert failing.attempts == 1  # no compact-and-retry
	assert _of(events, "run_error")[-1]["kind"] == "context_overflow"


async def test_model_retries_inside_the_adapter_never_rerun_completed_tools(tmp_path, monkeypatch):
	tool_runs = 0

	@tool
	async def count_once(*, ctx):
		nonlocal tool_runs
		tool_runs += 1
		return RuntimeToolResult(content="counted")

	class ToolThenFlakyModel(Model):
		"""Turn 1 calls a tool; turn 2 fails once inside its own retry envelope."""

		name = "tool-then-flaky"

		def __init__(self):
			self.calls = 0

		async def run(self, request: ModelRequest):
			def start_attempt():
				return self._attempt()

			async for event in run_with_retries(start_attempt, cancellation=request.cancellation):
				yield event

		async def _attempt(self):
			self.calls += 1
			if self.calls == 1:
				yield AssistantMessage(content=[ToolCall(id="count-1", name="count_once", arguments={})])
				yield Usage()
			elif self.calls == 2:
				raise ProviderError(
					kind="overloaded", retryable=True, status_code=503, provider="test", detail="busy"
				)
			else:
				yield AssistantMessage(content="done")
				yield Usage()

	monkeypatch.setitem(BUILTIN_TOOLS, "count_once", count_once)
	monkeypatch.setattr("flow.model.retry._retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path, tools=["count_once"], auto_approve=True)

	await _run(session, "go", model=ToolThenFlakyModel())

	assert tool_runs == 1
	assert [event["tool_call_id"] for event in _of(events, "tool_result")] == ["count-1"]
	assert [event["status"] for event in _of(events, "retry")] == ["scheduled", "started"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_overflow_recovery_survives_a_giant_message(tmp_path):
	# a message so large it overflowed on its own; the summarizer input must be
	# clipped and budgeted or the recovery call would overflow too
	session, events = _session(tmp_path, compact_threshold_tokens=1_000_000_000)
	giant = "y" * 600_000  # ~150k estimated tokens, over the 128k default window
	await _run(session, giant, model=MockModel(replies=[AssistantMessage(content="first")]))

	class RecordingOverflow(Model):
		name = "recording-overflow"

		def __init__(self):
			self.calls = 0
			self.summarizer_prompt_chars = 0

		async def run(self, request: ModelRequest):
			self.calls += 1
			if self.calls == 1:
				raise ProviderError(
					kind="context_overflow",
					retryable=False,
					status_code=400,
					provider="test",
					detail="too long",
				)
			if self.calls == 2:
				self.summarizer_prompt_chars = len(request.messages[0].content)
				yield AssistantMessage(content="## Goal\nsummary")
			else:
				yield AssistantMessage(content="recovered")
			yield Usage(input_tokens=5, output_tokens=5)

	model = RecordingOverflow()
	await _run(session, "continue", model=model)

	assert model.calls == 3
	assert 0 < model.summarizer_prompt_chars < 60_000  # the 600k message was clipped
	assert _of(events, "run_error") == []
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert session.transcript.messages[-1].text == "recovered"


async def test_abort_during_auto_compact_closes_the_pair(tmp_path):
	session, events = _session(tmp_path, compact_threshold_tokens=100)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first")]))

	class BlockingSummarizer(MockModel):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await asyncio.Event().wait()
			yield AssistantMessage(content="never")

	blocker = BlockingSummarizer()
	handle = await session.run("continue", model=blocker)
	await blocker.started.wait()  # the threshold summarizer is in flight
	session.abort()
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)

	assert _of(events, "compaction") == []
	ended = _of(events, "compaction_ended")[-1]
	assert ended["error_message"] == "aborted"
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


async def test_small_window_threshold_does_not_fire_on_a_small_conversation(tmp_path):
	# with the fixed 16k reserve a 10k window meant threshold=1: compaction on every
	# turn; the proportional reserve keeps it at window minus a quarter
	session, events = _session(tmp_path)
	mock = MockModel(
		replies=[AssistantMessage(content="one"), AssistantMessage(content="two")],
		context_window=10_000,
	)
	await _run(session, "first", model=mock)
	await _run(session, "second", model=mock)

	assert _of(events, "compaction_started") == []
	assert [event["context_window"] for event in _of(events, "usage")] == [10_000, 10_000]
	assert [e["reason"] for e in _of(events, "run_ended")] == ["done", "done"]


async def test_small_window_scales_the_retained_tail(tmp_path):
	session, events = _session(tmp_path)
	mock = MockModel(
		replies=[
			AssistantMessage(content="first"),
			AssistantMessage(content="small-window summary"),
			AssistantMessage(content="final"),
		],
		context_window=10_000,
	)
	await _run(session, "x" * 32_000, model=mock)
	await _run(session, "continue", model=mock)

	assert [event["reason"] for event in _of(events, "compaction")] == ["threshold"]
	assert session.transcript.messages[-1].text == "final"


async def test_disabled_auto_compaction_does_not_load_model_limits(tmp_path):
	class TrackingModel(MockModel):
		def __init__(self):
			super().__init__(replies=[AssistantMessage(content="done")])
			self.limit_loads = 0

		async def load_model_limits(self, cancellation=None):
			self.limit_loads += 1

	model = TrackingModel()
	session, _events = _session(tmp_path, auto_compact=False)
	await _run(session, "hello", model=model)

	assert model.limit_loads == 0
