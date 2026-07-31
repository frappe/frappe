"""The agent loop driven through its session: turns, hooks, the approval gate,
steering, abort at every await point, and typed failure settlement."""

import asyncio

import pytest

import flow_server.agent.loop as agent_loop
from flow_server.agent.loop import HookDecision
from flow_server.events import AssistantMessage, ToolCall, Usage
from flow_server.model import Model, ModelRequest, ProviderError, run_with_retries
from flow_server.model.auth import ResolvedModelAuth
from flow_server.model.mock import MockModel
from flow_server.session.config import SessionConfig
from flow_server.session.session import ResumeError, SessionConflict
from flow_server.session.store import SessionStore
from flow_server.tools import tool
from flow_server.tools.tool import ToolResult as RuntimeToolResult


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path), **cfg))
	return session, events


async def _run(session, message, **kwargs):
	submission = await session.run(message, **kwargs)
	assert submission.task is not None
	await submission.task
	return submission


async def _resume(session, answers, **kwargs):
	submission = await session.resume(answers, **kwargs)
	assert submission.task is not None
	await submission.task
	return submission


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


async def test_resume_deny_stops_run(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="unreached")])

	await _run(session, "read", model=mock)
	await _resume(session, {"c1": "Deny"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is True
	assert "denied" in tr["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
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

	monkeypatch.setattr("flow_server.agent.loop.resolve_model_auth", fail_auth)
	await _run(session, "hi")

	assert _of(events, "run_error")[0]["message"] == "RuntimeError: auth setup failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


async def test_run_wires_the_resolved_refresh_hook_into_the_model(tmp_path, monkeypatch):
	async def refresh(rejected_token):
		raise AssertionError("never called here")

	async def fake_resolve(model, store, *, provider_id=None):
		return ResolvedModelAuth(api_key="live", source="OAuth", provider_id="codex", refresh=refresh)

	captured = {}

	def fake_get_model(name, **kwargs):
		captured["name"] = name
		captured.update(kwargs)
		return MockModel(replies=[AssistantMessage(content="ok")])

	monkeypatch.setattr("flow_server.agent.loop.resolve_model_auth", fake_resolve)
	monkeypatch.setattr("flow_server.agent.loop.get_model", fake_get_model)
	session, events = _session(tmp_path, model="codex/test")

	await _run(session, "hello")

	assert captured["name"] == "codex/test"
	assert captured["api_key"] == "live"
	assert captured["refresh_auth"] is refresh
	assert [event["reason"] for event in _of(events, "run_ended")] == ["done"]


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

	submission = await session.run("wait", model=model)
	await model.started.wait()
	assert session.abort() is True
	assert submission.task is not None
	await asyncio.wait_for(submission.task, timeout=1)

	assert model.requests[0].cancellation is session.abort_signal
	assert model.closed.is_set()
	assert model.attempts == 1
	assert [event["stop_reason"] for event in _of(events, "assistant_message")] == ["aborted"]
	assert [event["reason"] for event in _of(events, "run_ended")] == ["aborted"]
	assert _of(events, "run_error") == []


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

	submission = await session.run("read", model=model, before_tool_call=before)
	await hook_started.wait()
	session.abort()
	assert submission.task is not None
	await asyncio.wait_for(submission.task, timeout=1)

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

	submission = await session.run("read", model=model, after_tool_call=after)
	await hook_started.wait()
	session.abort()
	assert submission.task is not None
	await asyncio.wait_for(submission.task, timeout=1)

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

	monkeypatch.setitem(agent_loop.BUILTIN_TOOLS, "first", first)
	monkeypatch.setitem(agent_loop.BUILTIN_TOOLS, "second", second)
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

	monkeypatch.setattr("flow_server.agent.client_tools.httpx.AsyncClient", BlockingClient)
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

	submission = await session.run("call client", model=model)
	await callback_started.wait()
	session.abort()
	assert submission.task is not None
	await asyncio.wait_for(submission.task, timeout=1)

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

	monkeypatch.setitem(agent_loop.BUILTIN_TOOLS, "count_once", count_once)
	monkeypatch.setattr("flow_server.model.base._retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path, tools=["count_once"], auto_approve=True)

	await _run(session, "go", model=ToolThenFlakyModel())

	assert tool_runs == 1
	assert [event["tool_call_id"] for event in _of(events, "tool_result")] == ["count-1"]
	assert [event["status"] for event in _of(events, "retry")] == ["scheduled", "started"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
