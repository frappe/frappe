import asyncio

import httpx
import pytest

import flow_server.agent.loop as agent_loop
from flow_server.agent import HookDecision, ResumeError, resume, run
from flow_server.events import AssistantMessage, TextDelta, ToolCall, Usage
from flow_server.model import Model, ModelRequest, ProviderError
from flow_server.model.mock import MockModel
from flow_server.model.resolver import ResolvedModelAuth
from flow_server.session.store import SessionConfig, SessionStore
from flow_server.tools import tool
from flow_server.tools.tool import ToolResult as RuntimeToolResult


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path), **cfg))
	return session, events


def _of(events, t):
	return [e for e in events if e["type"] == t]


def _read_call(cid="c1", path="a.txt"):
	return AssistantMessage(content=[ToolCall(id=cid, name="read_file", arguments={"path": path})])


async def test_full_turn_no_tools(tmp_path):
	session, events = _session(tmp_path)
	await run(session, "hi", model=MockModel(replies=[AssistantMessage(content="hello there")]))
	types = [e["type"] for e in events]
	assert "run_started" in types and "user_message" in types
	assert _of(events, "assistant_message")[0]["content"][0]["text"] == "hello there"
	assert _of(events, "run_ended")[0]["reason"] == "done"
	assert session.messages[0].type == "user_message"
	assert session.messages[0].content == "hi"


async def test_tool_call_runs_and_completes(tmp_path):
	(tmp_path / "a.txt").write_text("FILE-A")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="done")])
	await run(session, "read it", model=mock)
	tr = _of(events, "tool_result")
	assert len(tr) == 1
	assert tr[0]["content"] == "FILE-A"
	assert tr[0]["is_error"] is False
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_agent_propagates_allowed_roots_to_path_tools(tmp_path):
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
	mock = MockModel(
		replies=[
			_read_call(path="../secret.txt"),
			AssistantMessage(content="done"),
		]
	)

	await run(session, "read outside the project", model=mock)

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

	await run(session, "read", model=mock, before_tool_call=before)
	assert _of(events, "tool_result")[0]["content"] == "BBB"  # hook redirected the read


async def test_before_hook_blocks(tmp_path):
	(tmp_path / "a.txt").write_text("AAA")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="ok")])

	def before(tc, ctx):
		return HookDecision(result="[blocked by policy]", is_error=True)

	await run(session, "read", model=mock, before_tool_call=before)
	tr = _of(events, "tool_result")[0]
	assert tr["content"] == "[blocked by policy]"
	assert tr["is_error"] is True


async def test_after_hook_rewrites_result(tmp_path):
	(tmp_path / "a.txt").write_text("sensitive-token-123")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="ok")])

	def after(tc, result):
		return "[redacted]" if "sensitive" in result.content else None

	await run(session, "read", model=mock, after_tool_call=after)
	assert _of(events, "tool_result")[0]["content"] == "[redacted]"


async def test_pause_and_resume(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	session, events = _session(tmp_path, confirm_tools=["read_file"])
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="all done")])

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
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="unreached")])

	await run(session, "read", model=mock)
	await resume(session, {"c1": "Deny"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is True
	assert "denied" in tr["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert mock._turn == 1  # the model was NOT called again after denial


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
	await run(session, "read", model=mock)
	approval_seq = _of(events, "approval_required")[0]["seq"]
	latest_seq = session.log.latest_seq
	session.abort.set()

	with pytest.raises(ResumeError, match="missing answers for: c2"):
		await resume(
			session,
			{"c1": "Approve"},
			approval_seq=approval_seq,
			model=mock,
		)
	with pytest.raises(ResumeError, match="stale"):
		await resume(
			session,
			{"c1": "Approve", "c2": "Approve"},
			approval_seq=approval_seq - 1,
			model=mock,
		)

	assert session.log.latest_seq == latest_seq
	assert session.abort.is_set()
	assert _of(events, "tool_result") == []


async def test_non_streaming_run(tmp_path):
	session, events = _session(tmp_path, stream=False)
	await run(session, "hi", model=MockModel(replies=[AssistantMessage(content="hi there friend")]))
	assert _of(events, "text_delta") == []  # no live deltas in non-streaming mode
	assert _of(events, "assistant_message")[0]["content"][0]["text"] == "hi there friend"
	assert _of(events, "run_ended")[0]["reason"] == "done"


async def test_length_stop_is_not_reported_as_done(tmp_path):
	session, events = _session(tmp_path)
	reply = AssistantMessage(content="partial", stop_reason="length")

	await run(session, "hi", model=MockModel(replies=[reply]))

	assert _of(events, "assistant_message")[0]["stop_reason"] == "length"
	assert _of(events, "run_ended")[0]["reason"] == "length"


async def test_max_turns_cap(tmp_path):
	(tmp_path / "a.txt").write_text("x")
	session, events = _session(tmp_path, max_turns=2)
	# model keeps calling a tool every turn; the cap must stop it
	mock = MockModel(replies=[_read_call("c1"), _read_call("c2"), _read_call("c3")])
	await run(session, "loop", model=mock)
	assert _of(events, "run_ended")[0]["reason"] == "max_turns"
	assert len(_of(events, "tool_result")) == 2


async def test_setup_failure_emits_one_terminal_error(tmp_path, monkeypatch):
	session, events = _session(tmp_path)

	async def fail_auth(*args, **kwargs):
		raise RuntimeError("auth setup failed")

	monkeypatch.setattr("flow_server.agent.loop.resolve_model_auth", fail_auth)
	await run(session, "hi")

	assert _of(events, "run_error")[0]["message"] == "RuntimeError: auth setup failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


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

	await run(session, "read", model=mock, before_tool_call=fail_before)

	results = _of(events, "tool_result")
	assert [result["tool_call_id"] for result in results] == ["c1", "c2"]
	assert all(result["is_error"] for result in results)
	assert all(result["details"]["transcript_repair"]["reason"] == "interrupted" for result in results)
	assert _of(events, "run_error")[0]["message"] == "RuntimeError: hook failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]
	assert [message.type for message in session.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	latest_seq = session.log.latest_seq
	reloaded = SessionStore(str(tmp_path)).get(session.id)
	assert reloaded.log.latest_seq == latest_seq


async def test_model_stream_failure_repairs_persisted_assistant_calls(tmp_path, monkeypatch):
	session, events = _session(tmp_path)
	mock = MockModel()

	async def fail_after_assistant(request):
		yield _read_call()
		raise RuntimeError("stream failed")

	monkeypatch.setattr(mock, "run", fail_after_assistant)
	await run(session, "read", model=mock)

	assert [result["tool_call_id"] for result in _of(events, "tool_result")] == ["c1"]
	assert _of(events, "run_error")[0]["message"] == "RuntimeError: stream failed"
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]
	assert [message.type for message in session.messages] == [
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
	await run(session, "hi", model=mock)

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

	task = asyncio.create_task(run(session, "wait", model=model))
	await model.started.wait()
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

	assert model.requests[0].cancellation is session.abort
	assert model.closed.is_set()
	assert model.attempts == 1
	assert [event["stop_reason"] for event in _of(events, "assistant_message")] == ["aborted"]
	assert [event["reason"] for event in _of(events, "run_ended")] == ["aborted"]
	assert _of(events, "run_error") == []


async def test_abort_during_provider_retry_delay_prevents_next_attempt(tmp_path):
	class RetryDelayModel(Model):
		name = "retry-delay"

		def __init__(self):
			self.attempts = 0
			self.delay_started = asyncio.Event()

		async def run(self, request: ModelRequest):
			for _ in range(3):
				self.attempts += 1
				self.delay_started.set()
				await asyncio.sleep(60)
			if False:
				yield

	session, events = _session(tmp_path)
	model = RetryDelayModel()
	task = asyncio.create_task(run(session, "retry", model=model))
	await model.delay_started.wait()
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

	assert model.attempts == 1
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


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

	task = asyncio.create_task(run(session, "read", model=model, before_tool_call=before))
	await hook_started.wait()
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

	assert hook_cancelled.is_set()
	results = _of(events, "tool_result")
	assert len(results) == 1
	assert results[0]["details"]["transcript_repair"]["reason"] == "interrupted"
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

	task = asyncio.create_task(run(session, "read", model=model, after_tool_call=after))
	await hook_started.wait()
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

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

	await run(session, "go", model=model)

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

	monkeypatch.setattr("flow_server.agent.loop.httpx.AsyncClient", BlockingClient)
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

	task = asyncio.create_task(run(session, "call client", model=model))
	await callback_started.wait()
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

	assert callback_cancelled.is_set()
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


class _FlakyProviderModel(Model):
	name = "flaky"
	provider = "test"
	api = "test"
	model = "test/flaky"

	def __init__(self, failures: list[ProviderError]):
		self.failures = failures
		self.attempts = 0

	async def run(self, request: ModelRequest):
		self.attempts += 1
		if self.failures:
			yield TextDelta(text=f"partial-{self.attempts}")
			raise self.failures.pop(0)
		yield AssistantMessage(content="done", provider=self.provider, model=self.model)
		yield Usage(output_tokens=1)


def _provider_error(kind="overloaded", *, retryable=True, detail="provider busy"):
	return ProviderError(
		kind=kind,
		retryable=retryable,
		status_code=503,
		provider="test",
		detail=detail,
	)


async def test_transient_provider_failure_retries_before_committing_assistant(tmp_path, monkeypatch):
	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path)
	model = _FlakyProviderModel([_provider_error()])

	await run(session, "try", model=model)

	assert model.attempts == 2
	assert [event["attempt"] for event in _of(events, "retry_scheduled")] == [2]
	assert [event["max_attempts"] for event in _of(events, "retry_scheduled")] == [3]
	assert [event["attempt"] for event in _of(events, "retry_started")] == [2]
	assert _of(events, "retry_exhausted") == []
	assert [event["content"][0]["text"] for event in _of(events, "assistant_message")] == ["done"]
	assert [row["type"] for row in session.log.read_since(0)].count("assistant_message") == 1
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_retry_exhaustion_has_one_typed_error_lifecycle(tmp_path, monkeypatch):
	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path)
	model = _FlakyProviderModel([_provider_error(), _provider_error(), _provider_error()])

	await run(session, "try", model=model)

	assert model.attempts == 3
	assert len(_of(events, "retry_scheduled")) == 2
	assert len(_of(events, "retry_started")) == 2
	assert _of(events, "retry_exhausted") == [
		{
			"type": "retry_exhausted",
			"attempts": 3,
			"kind": "overloaded",
		}
	]
	assert len(_of(events, "assistant_message")) == 1
	assert _of(events, "assistant_message")[0]["stop_reason"] == "error"
	assert len(_of(events, "run_error")) == 1
	assert _of(events, "run_error")[0]["kind"] == "overloaded"
	assert _of(events, "run_error")[0]["status_code"] == 503
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]


async def test_nonretryable_provider_failure_fails_immediately(tmp_path):
	session, events = _session(tmp_path)
	model = _FlakyProviderModel([_provider_error("invalid_request", retryable=False, detail="bad input")])

	await run(session, "try", model=model)

	assert model.attempts == 1
	assert _of(events, "retry_scheduled") == []
	assert _of(events, "retry_started") == []
	assert _of(events, "retry_exhausted") == []
	assert _of(events, "run_error")[0]["kind"] == "invalid_request"


async def test_context_overflow_ends_cleanly_without_retry(tmp_path):
	session, events = _session(tmp_path)
	model = _FlakyProviderModel(
		[_provider_error("context_overflow", retryable=False, detail="context_length_exceeded")]
	)

	await run(session, "too much", model=model)

	assert model.attempts == 1
	assert _of(events, "retry_scheduled") == []
	assert _of(events, "run_error")[0]["kind"] == "context_overflow"
	assert _of(events, "run_error")[0]["detail"] == "context_length_exceeded"
	assert _of(events, "run_ended")[0]["reason"] == "error"


async def test_oversized_provider_retry_hint_is_not_slept_out(tmp_path):
	session, events = _session(tmp_path)
	model = _FlakyProviderModel(
		[
			ProviderError(
				kind="rate_limit",
				retryable=True,
				status_code=429,
				provider="test",
				detail="daily limit reached",
				retry_after_seconds=3600,
			)
		]
	)

	await run(session, "try", model=model)

	assert model.attempts == 1
	assert _of(events, "retry_scheduled") == []
	assert _of(events, "retry_exhausted") == []
	assert _of(events, "run_error")[0]["kind"] == "rate_limit"
	assert _of(events, "run_ended")[-1]["reason"] == "error"


async def test_retry_started_separates_a_replayed_stream(tmp_path, monkeypatch):
	"""A failed attempt's live deltas are already out, so `retry_started` is the
	boundary at which a client drops the in-flight turn's streamed text."""

	class RestreamingModel(Model):
		name = "restreaming"

		def __init__(self):
			self.attempts = 0

		async def run(self, request: ModelRequest):
			self.attempts += 1
			yield TextDelta(text="the plan is ")
			if self.attempts == 1:
				raise _provider_error()
			yield TextDelta(text="to ship it")
			yield AssistantMessage(content="the plan is to ship it")
			yield Usage()

	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path)

	await run(session, "plan", model=RestreamingModel())

	timeline = [event["type"] for event in events]
	boundary = timeline.index("retry_started")
	assert timeline[:boundary].count("text_delta") == 1
	assert timeline[boundary:].count("text_delta") == 2
	assert [row["type"] for row in session.log.read_since(0)].count("assistant_message") == 1


async def test_cancellation_interrupts_retry_backoff(tmp_path, monkeypatch):
	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 60)
	session, events = _session(tmp_path)
	model = _FlakyProviderModel([_provider_error()])

	task = asyncio.create_task(run(session, "try", model=model))
	for _ in range(100):
		if _of(events, "retry_scheduled"):
			break
		await asyncio.sleep(0.01)
	session.request_abort()
	await asyncio.wait_for(task, timeout=1)

	assert model.attempts == 1
	assert _of(events, "retry_started") == []
	assert _of(events, "retry_exhausted") == []
	assert _of(events, "assistant_message")[-1]["stop_reason"] == "aborted"
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"


async def test_model_retry_never_reruns_completed_tools(tmp_path, monkeypatch):
	tool_runs = 0

	@tool
	async def count_once(*, ctx):
		nonlocal tool_runs
		tool_runs += 1
		return RuntimeToolResult(content="counted")

	class ToolThenFlakyModel(Model):
		name = "tool-then-flaky"

		def __init__(self):
			self.calls = 0

		async def run(self, request: ModelRequest):
			self.calls += 1
			if self.calls == 1:
				yield AssistantMessage(content=[ToolCall(id="count-1", name="count_once", arguments={})])
				yield Usage()
			elif self.calls == 2:
				raise _provider_error()
			else:
				yield AssistantMessage(content="done")
				yield Usage()

	monkeypatch.setitem(agent_loop.BUILTIN_TOOLS, "count_once", count_once)
	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path, tools=["count_once"], auto_approve=True)

	await run(session, "go", model=ToolThenFlakyModel())

	assert tool_runs == 1
	assert [event["tool_call_id"] for event in _of(events, "tool_result")] == ["count-1"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_expired_oauth_refreshes_and_reresolves_model_once(tmp_path, monkeypatch):
	resolutions: list[str | None] = []

	async def resolve_auth(model, store, *, credential_id=None, refresh_access_token=None):
		resolutions.append(refresh_access_token)
		token = "fresh-token" if refresh_access_token else "expired-token"
		return ResolvedModelAuth(
			api_key=token,
			source="OAuth",
			provider_id="codex",
		)

	class TokenModel(Model):
		name = "codex/test"

		def __init__(self, token):
			self.token = token

		async def run(self, request: ModelRequest):
			if self.token == "expired-token":
				raise ProviderError(
					kind="auth",
					retryable=True,
					status_code=401,
					provider="codex",
					detail="access token expired",
				)
			yield AssistantMessage(content="authenticated")
			yield Usage()

	monkeypatch.setattr(agent_loop, "resolve_model_auth", resolve_auth)
	monkeypatch.setattr(agent_loop, "get_model", lambda name, *, api_key=None, **kwargs: TokenModel(api_key))
	session, events = _session(tmp_path, model="codex/test")

	await run(session, "hello")

	assert resolutions == [None, "expired-token"]
	assert [event["attempt"] for event in _of(events, "retry_scheduled")] == [2]
	assert [event["max_attempts"] for event in _of(events, "retry_scheduled")] == [4]
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_credential_refresh_failure_ends_the_run_typed(tmp_path, monkeypatch):
	"""The token endpoint is a second provider call; its transport faults must not
	escape the loop untyped."""

	async def resolve_auth(model, store, *, credential_id=None, refresh_access_token=None):
		if refresh_access_token is not None:
			raise httpx.ConnectError("token endpoint unreachable")
		return ResolvedModelAuth(api_key="expired-token", source="OAuth", provider_id="codex")

	class ExpiredModel(Model):
		name = "codex/test"

		async def run(self, request: ModelRequest):
			raise ProviderError(
				kind="auth",
				retryable=True,
				status_code=401,
				provider="codex",
				detail="access token expired",
			)
			yield  # pragma: no cover - unreachable, keeps `run` an async generator

	monkeypatch.setattr(agent_loop, "resolve_model_auth", resolve_auth)
	monkeypatch.setattr(agent_loop, "get_model", lambda name, **kwargs: ExpiredModel())
	session, events = _session(tmp_path, model="codex/test")

	await run(session, "hello")

	assert [event["attempt"] for event in _of(events, "retry_scheduled")] == [2]
	assert _of(events, "retry_started") == []
	assert [event["kind"] for event in _of(events, "retry_exhausted")] == ["auth"]
	assert len(_of(events, "assistant_message")) == 1
	assert _of(events, "assistant_message")[0]["stop_reason"] == "error"
	run_error = _of(events, "run_error")[0]
	assert (run_error["kind"], run_error["retryable"]) == ("auth", False)
	assert "token endpoint unreachable" in run_error["detail"]
	assert [event["reason"] for event in _of(events, "run_ended")] == ["error"]
