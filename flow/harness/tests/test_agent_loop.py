"""The agent loop driven through its session: turns, hooks, the approval gate,
steering, abort at every await point, and typed failure settlement."""

import asyncio

import pytest

from flow_harness.agent.client_tools import deliver_result
from flow_harness.agent.loop import HookDecision
from flow_harness.events import AssistantMessage, ToolCall, Usage
from flow_harness.model import Model, ModelRequest, ProviderError, run_with_retries
from flow_harness.model.auth import ResolvedModelAuth
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.mock import MockModel
from flow_harness.session.config import SessionConfig
from flow_harness.session.session import ResumeError, SessionConflict
from flow_harness.session.store import SessionStore
from flow_harness.tools import BUILTIN_TOOLS, tool
from flow_harness.tools.tool import ToolResult as RuntimeToolResult


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(
		str(tmp_path),
		event_sink=lambda _sid, ev: events.append(ev),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),  # never the real one
	)
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
	return AssistantMessage(content=[ToolCall(id=cid, name="read", arguments={"path": path})])


def _offer(cid, *replies):
	return ToolCall(id=cid, name="suggest_replies", arguments={"replies": list(replies)})


async def test_a_run_takes_turns_until_the_model_stops_or_calls_only_run_ending_tools(tmp_path):
	(tmp_path / "a.txt").write_text("FILE-A")
	session, events = _session(tmp_path)
	mock = MockModel(replies=[_read_call(), AssistantMessage(content="hello there")])
	await _run(session, "hi", model=mock)
	types = [e["type"] for e in events]
	assert "run_started" in types and "user_message" in types
	[result] = _of(events, "tool_result")
	assert result["content"] == "FILE-A"
	assert result["is_error"] is False
	assert _of(events, "assistant_message")[-1]["content"][0]["text"] == "hello there"
	assert [e["reason"] for e in _of(events, "run_ended")] == ["done"]
	assert session.transcript.messages[0].type == "user_message"
	assert session.transcript.messages[0].content == "hi"

	# offering replies ends the run, unless the turn also called another tool or the offer failed
	session, events = _session(tmp_path, tools=["read", "suggest_replies"])
	read, offer = _read_call().tool_calls[0], _offer("c2", "Yes", "No")
	turns = [[read, offer], [_offer("c3", "Yes")], [_offer("c4", "Yes", "No")], "never asked"]
	mock = MockModel(replies=[AssistantMessage(content=content) for content in turns])
	await _run(session, "hi", model=mock)
	assert [r["is_error"] for r in _of(events, "tool_result")] == [False, False, True, False]
	assert len(_of(events, "assistant_message")) == 3
	assert [e["reason"] for e in _of(events, "run_ended")] == ["done"]


async def test_the_model_request_carries_the_session_settings(tmp_path, monkeypatch):
	@tool(display_template="Searching the web for {{ query }}")
	async def web_search(query: str, *, ctx) -> RuntimeToolResult:
		del ctx
		return RuntimeToolResult(content=query)

	async def post(config, url, payload):
		return {"content": "built"}

	def schema(name):
		return {
			"type": "function",
			"function": {
				"name": name,
				"description": "build",
				"parameters": {"type": "object", "properties": {"year": {"type": "integer"}}},
			},
		}

	async def first_request(injected=True, **settings):
		session, events = _session(
			tmp_path,
			client_tools=[
				{**schema("report"), "display_template": "Building {{ year }}"},
				{**schema("broken"), "display_template": "Building {{ year | upper }}"},
			],
			callback_url="https://client.invalid/tools",
			**settings,
		)
		assert session.server_tools is not None
		session.server_tools[web_search.name] = web_search
		call = ToolCall(id="c1", name="broken", arguments={"year": 2026})
		model = _RecordingModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])
		if not injected:  # built from the session's model name instead
			monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda name, **kwargs: model)
		await _run(session, "build the report", model=model if injected else None)
		# a malformed client template is skipped, not fatal
		assert [r["content"] for r in _of(events, "tool_result")] == ["built"]
		assert _of(events, "run_ended")[-1]["reason"] == "done"
		return model.requests[0], events

	monkeypatch.setattr("flow_harness.agent.client_tools._post", post)
	request, _ = await first_request()
	assert request.tool_display_templates["web_search"] == "Searching the web for {{ query }}"
	# a client tool's template reaches the UI; the model gets its schema without it
	assert request.tool_display_templates["report"] == "Building {{ year }}"
	assert "broken" not in request.tool_display_templates
	assert schema("report") in request.tools
	assert request.params is None

	request, events = await first_request(stream=False, reasoning_effort="high")
	assert request.params["reasoning_effort"] == "high"
	assert request.stream is False
	assert _of(events, "text_delta") == []  # no live deltas in non-streaming mode
	assert _of(events, "assistant_message")[-1]["content"][0]["text"] == "done"

	request, _ = await first_request(injected=False, reasoning_effort="high")
	assert request.params["reasoning_effort"] == "high"


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


async def test_hooks_rewrite_arguments_block_calls_and_rewrite_results(tmp_path):
	for name, text in (("a.txt", "AAA"), ("b.txt", "BBB"), ("s.txt", "sensitive-token-123")):
		(tmp_path / name).write_text(text)
	session, events = _session(tmp_path)
	reads = AssistantMessage(
		content=[
			ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
			ToolCall(id="c2", name="read", arguments={"path": "a.txt"}),
			ToolCall(id="c3", name="read", arguments={"path": "s.txt"}),
		]
	)

	def before(tc, ctx):
		if tc.id == "c1":
			return HookDecision(args={"path": "b.txt"})
		if tc.id == "c2":
			return HookDecision(result="[blocked by policy]", is_error=True)
		return None

	def after(tc, result):
		return "[redacted]" if "sensitive" in result.content else None

	mock = MockModel(replies=[reads, AssistantMessage(content="ok")])
	await _run(session, "read", model=mock, before_tool_call=before, after_tool_call=after)

	# c1 was redirected to b.txt, c2 blocked, c3 redacted
	assert [(r["content"], r["is_error"]) for r in _of(events, "tool_result")] == [
		("BBB", False),
		("[blocked by policy]", True),
		("[redacted]", False),
	]


async def _dump(session, events, content):
	"""Run a tool that returns `content`; return its tool_result event."""

	@tool
	async def dump(*, ctx):
		return RuntimeToolResult(content=content)

	assert session.server_tools is not None
	session.server_tools[dump.name] = dump
	call = AssistantMessage(content=[ToolCall(id="c1", name="dump", arguments={})])
	await _run(session, "dump", model=MockModel(replies=[call, AssistantMessage(content="ok")]))
	return _of(events, "tool_result")[-1]


async def test_oversized_tool_results_keep_their_start_and_end(tmp_path):
	session, events = _session(tmp_path)
	result = await _dump(session, events, "a" * 100_000 + "b" * 100_000)
	assert result["content"] == (
		"a" * 40_960 + "\n\n[Cut the middle: showing the first 40 KB and the last 10 KB of 195 KB. "
		"To see more, call again asking for less: fewer fields, filters, a limit or a count. "
		"Don't repeat a call that changed data.]\n\n" + "b" * 10_240
	)
	assert result["details"]["truncation"]["truncated"] is True
	assert result["details"]["truncation"]["output_lines"] == 1  # both ends are parts of one line

	# a trailing newline keeps the end
	result = await _dump(session, events, "a" * 100_000 + "b" * 100_000 + "\n")
	assert result["content"].endswith("]\n\n" + "b" * 10_239 + "\n")

	# a long list keeps most lines from its start
	result = await _dump(session, events, "\n".join(str(i) for i in range(5000)))
	head, note, tail = result["content"].split("\n\n")
	assert head.split("\n") == [str(i) for i in range(1600)]
	assert tail.split("\n") == [str(i) for i in range(4600, 5000)]
	assert note.startswith("[Cut the middle")
	assert result["details"]["truncation"]["output_lines"] == 2000

	# a tool that cuts its own output is not cut again
	(tmp_path / "a.txt").write_text("line\n" * 3000)

	async def read(**hooks):
		mock = MockModel(replies=[_read_call(), AssistantMessage(content="ok")])
		await _run(session, "read", model=mock, **hooks)
		return _of(events, "tool_result")[-1]["content"]

	content = await read()
	assert content.endswith("use offset=2001 to continue]")
	assert "Cut the middle" not in content

	# a hook that grows the cut result, or answers the call itself, is still capped
	content = await read(after_tool_call=lambda tc, result: "y" * 200_000)
	assert content.startswith("y" * 40_960 + "\n\n[Cut the middle") and content.endswith(
		"]\n\n" + "y" * 10_240
	)
	content = await read(before_tool_call=lambda tc, ctx: HookDecision(result="z" * 200_000))
	assert content.startswith("z" * 40_960 + "\n\n[Cut the middle") and content.endswith(
		"]\n\n" + "z" * 10_240
	)


async def test_resume_approves_denies_or_redirects_the_paused_call(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")

	async def paused(reply):
		session, events = _session(tmp_path, confirm_tools=["read"])
		mock = MockModel(replies=[_read_call(), AssistantMessage(content=reply)])
		await _run(session, "read", model=mock)
		[approval] = _of(events, "approval_required")
		assert [call["id"] for call in approval["calls"]] == ["c1"]
		assert _of(events, "run_ended")[0]["reason"] == "paused"
		assert _of(events, "tool_result") == []  # gated tool did not run
		return session, events, mock

	session, events, mock = await paused("all done")
	budget = session._budget
	assert budget.spent > 0
	await _resume(session, {"c1": "Approve"}, model=mock)
	assert _of(events, "tool_result")[0]["content"] == "SECRET"
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert len(_of(events, "run_started")) == 2  # the resumed run announces itself
	assert session._budget is budget  # approving did not hand the run a fresh ceiling
	await _run(session, "again", model=MockModel(replies=[AssistantMessage(content="ok")]))
	assert session._budget is not budget

	session, events, mock = await paused("unreached")
	await _resume(session, {"c1": "Deny"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is True
	assert "denied" in tr["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "denied"
	assert mock._turn == 1  # the model was NOT called again after denial

	session, events, mock = await paused("adjusted")
	await _resume(session, {"c1": "use the other file"}, model=mock)
	tr = _of(events, "tool_result")[0]
	assert tr["is_error"] is False
	assert "use the other file" in tr["content"]
	assert mock._turn == 2  # the model got a turn to adjust
	assert _of(events, "run_ended")[-1]["reason"] == "done"

	# an approved run-ending tool still ends the run; a redirect still gets the model's turn
	for answer, model_turns in [("Approve", 1), ("shorter ones", 2)]:
		session, events = _session(tmp_path, tools=["suggest_replies"], confirm_tools=["suggest_replies"])
		replies = [
			AssistantMessage(content=[_offer("c1", "Yes", "No")]),
			AssistantMessage(content="adjusted"),
		]
		mock = MockModel(replies=replies)
		await _run(session, "ask me", model=mock)
		await _resume(session, {"c1": answer}, model=mock)
		assert mock._turn == model_turns, answer
		assert [e["reason"] for e in _of(events, "run_ended")] == ["paused", "done"]


async def test_a_paused_session_refuses_runs_and_inexact_answers_until_cancelled(tmp_path):
	# confirm_tools adds gates on top of each tool's default: naming one tool keeps bash gated
	session, events = _session(tmp_path, confirm_tools=["send_email"])
	calls = [ToolCall(id=cid, name="bash", arguments={"command": "pwd"}) for cid in ("c1", "c2")]
	await _run(session, "run it", model=MockModel(replies=[AssistantMessage(content=calls)]))
	assert _of(events, "tool_result") == []  # bash stayed gated
	[approval] = _of(events, "approval_required")
	assert [call["id"] for call in approval["calls"]] == ["c1", "c2"]
	assert _of(events, "run_ended")[0]["reason"] == "paused"
	assert session.state == "paused"
	latest_seq = session.log.latest_seq

	with pytest.raises(SessionConflict, match="paused for approval"):
		await session.run("something else", model=MockModel())
	with pytest.raises(ResumeError, match="missing answers for: c2"):
		await session.resume({"c1": "Approve"}, approval_seq=approval["seq"], model=MockModel())
	with pytest.raises(ResumeError, match="stale"):
		answers = {"c1": "Approve", "c2": "Approve"}
		await session.resume(answers, approval_seq=approval["seq"] - 1, model=MockModel())
	assert session.log.latest_seq == latest_seq
	assert _of(events, "tool_result") == []

	assert await session.cancel_pending() is True
	assert session.state == "idle"
	assert session.transcript.pending_approval is None
	cancelled = _of(events, "tool_result")
	assert [r["tool_call_id"] for r in cancelled] == ["c1", "c2"]
	assert all("cancelled" in r["content"] and r["is_error"] for r in cancelled)

	# the session is usable again
	await _run(session, "hi", model=MockModel(replies=[AssistantMessage(content="fresh")]))
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert await session.cancel_pending() is False  # nothing pending anymore


async def test_steering_joins_the_active_run_and_is_dropped_when_it_ends(tmp_path):
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

	# a steer waiting on a tool turn reaches the run resumed after an approval
	(tmp_path / "a.txt").write_text("x")
	session, events = _session(tmp_path, confirm_tools=["read"])
	await _steer_into_a_tool_turn(session)
	await _resume(session, {"c1": "Approve"}, model=MockModel(replies=[AssistantMessage(content="ok")]))
	assert [e["content"] for e in _of(events, "user_message")] == ["start", "steer me"]

	# but dies with a run that ends
	cases = [
		# session config, how the paused run ends, the run ends seen
		({"confirm_tools": ["read"]}, "deny", ["paused", "denied"]),
		({"confirm_tools": ["read"]}, "cancel", ["paused"]),
		({"max_turns": 1}, None, ["max_turns"]),
		({"token_budget": 5}, None, ["budget"]),
	]
	for config, ending, ends in cases:
		session, events = _session(tmp_path, **config)
		await _steer_into_a_tool_turn(session)
		if ending == "deny":
			await _resume(session, {"c1": "Deny"})
		elif ending == "cancel":
			assert await session.cancel_pending() is True
		assert [e["reason"] for e in _of(events, "run_ended")] == ends, ending

		await _run(session, "next", model=MockModel(replies=[AssistantMessage(content="ok")]))

		assert [e["content"] for e in _of(events, "user_message")] == ["start", "next"], ends


async def _steer_into_a_tool_turn(session):
	"""Start a run, steer it while its model is busy, then let the model ask to read a.txt."""
	model = _SlowReader()
	handle = await session.run("start", model=model)
	await model.started.wait()
	assert (await session.run("steer me")).status == "steered"
	model.release.set()
	await handle.task


class _SlowReader(Model):
	name = "slow-reader"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()

	async def run(self, request: ModelRequest):
		self.started.set()
		await self.release.wait()
		yield _read_call()
		yield Usage(output_tokens=10)


async def test_a_length_stop_or_the_turn_cap_ends_the_run_early(tmp_path):
	session, events = _session(tmp_path)
	await _run(
		session, "hi", model=MockModel(replies=[AssistantMessage(content="partial", stop_reason="length")])
	)
	assert _of(events, "assistant_message")[0]["stop_reason"] == "length"
	assert _of(events, "run_ended")[0]["reason"] == "length"  # not reported as done

	# a truncated turn's calls fail without running
	session, events = _session(tmp_path)
	truncated = AssistantMessage(
		content=[
			ToolCall(id="c1", name="write", arguments={"path": "a.txt", "content": "x"}),
			ToolCall(id="c2", name="write", arguments={"path": "b.txt", "content": "y"}),
		],
		stop_reason="length",
	)
	await _run(
		session, "write them", model=MockModel(replies=[truncated, AssistantMessage(content="retried")])
	)
	results = _of(events, "tool_result")
	assert [r["tool_call_id"] for r in results] == ["c1", "c2"]
	assert all(r["is_error"] and "truncated" in r["content"] for r in results)
	assert not (tmp_path / "a.txt").exists() and not (tmp_path / "b.txt").exists()
	# the model still gets a turn to re-issue the calls
	assert _of(events, "run_ended")[0]["reason"] == "done"

	# the turn cap stops a model that keeps calling a tool
	session, events = _session(tmp_path, max_turns=2)
	await _run(
		session, "loop", model=MockModel(replies=[_read_call("c1"), _read_call("c2"), _read_call("c3")])
	)
	assert _of(events, "run_ended")[0]["reason"] == "max_turns"
	assert len(_of(events, "tool_result")) == 2


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

	monkeypatch.setattr("flow_harness.agent.loop.resolve_model_auth", fake_resolve)
	monkeypatch.setattr("flow_harness.agent.loop.get_model", fake_get_model)
	session, events = _session(tmp_path, model="codex/test")

	await _run(session, "hello")

	assert captured["name"] == "codex/test"
	assert captured["api_key"] == "live"
	assert captured["refresh_auth"] is refresh
	assert [event["reason"] for event in _of(events, "run_ended")] == ["done"]


class _RecordingModel(MockModel):
	"""Keeps every request it served."""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.requests: list[ModelRequest] = []

	async def run(self, request):
		self.requests.append(request)
		async for event in super().run(request):
			yield event


async def test_a_failing_run_settles_with_one_typed_error(tmp_path, monkeypatch):
	async def fail_auth(*args, **kwargs):
		raise RuntimeError("auth setup failed")

	def fail_hook(tc, ctx):
		raise RuntimeError("hook failed")

	async def fail_after_assistant(request):
		yield _read_call()
		raise RuntimeError("stream failed")

	async def empty_stream(request):
		if False:
			yield

	def streaming(run):
		model = MockModel()
		model.run = run
		return model

	monkeypatch.setattr("flow_harness.agent.loop.resolve_model_auth", fail_auth)
	two_reads = AssistantMessage(
		content=[
			ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
			ToolCall(id="c2", name="read", arguments={"path": "b.txt"}),
		]
	)
	provider = _FailingModel(
		ProviderError(
			kind="invalid_request", retryable=False, status_code=400, provider="test", detail="bad input"
		)
	)
	overflow = _FailingModel(
		ProviderError(
			kind="context_overflow",
			retryable=False,
			status_code=400,
			provider="test",
			detail="context_length_exceeded",
		)
	)
	cases = [
		# case, model, run hooks, run_error fields, calls the settlement closed
		("setup", None, {}, {"message": "RuntimeError: auth setup failed"}, []),
		(
			"hook",
			MockModel(replies=[two_reads]),
			{"before_tool_call": fail_hook},
			{"message": "RuntimeError: hook failed"},
			["c1", "c2"],
		),
		("stream", streaming(fail_after_assistant), {}, {"message": "RuntimeError: stream failed"}, ["c1"]),
		(
			"empty stream",
			streaming(empty_stream),
			{},
			{"message": "RuntimeError: model stream ended without an assistant message"},
			[],
		),
		(
			"provider",
			provider,
			{},
			{"kind": "invalid_request", "retryable": False, "status_code": 400, "detail": "bad input"},
			[],
		),
		# nothing is old enough to compact, so the overflow ends the run
		("overflow", overflow, {}, {"kind": "context_overflow", "detail": "context_length_exceeded"}, []),
	]
	for name, model, hooks, error, closed in cases:
		session, events = _session(tmp_path)
		await _run(session, "go", model=model, **hooks)

		[run_error] = _of(events, "run_error")
		assert {key: run_error[key] for key in error} == error, name
		assert [event["reason"] for event in _of(events, "run_ended")] == ["error"], name
		results = _of(events, "tool_result")
		assert [result["tool_call_id"] for result in results] == closed, name
		assert all(
			result["is_error"] and result["details"]["repair"] == "interrupted" for result in results
		), name
		turn = ["assistant_message", *["tool_result"] * len(closed)] if closed else []
		assert [message.type for message in session.transcript.messages] == ["user_message", *turn], name
		reloaded = SessionStore(str(tmp_path)).get(session.id)
		assert reloaded.log.latest_seq == session.log.latest_seq, name  # settlement already closed the turn
	assert provider.attempts == 1


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


async def test_an_aborted_model_turn_ends_the_run_and_closes_its_calls(tmp_path):
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

	# a turn the model itself ends as aborted can still carry tool calls; the loop must answer them
	aborted = AssistantMessage(
		content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})],
		stop_reason="aborted",
	)
	await _run(session, "go", model=MockModel(replies=[aborted]))
	[result] = _of(events, "tool_result")
	assert result["tool_call_id"] == "c1"
	assert result["is_error"] is True
	assert "aborted" in result["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"
	assert session.transcript.missing_results() == ()  # a reload would repair nothing


async def test_abort_cancels_a_blocked_hook_or_client_callback(tmp_path, monkeypatch):
	started = asyncio.Event()
	cancelled = asyncio.Event()

	async def block(*_args, **_kwargs):
		started.set()
		try:
			await asyncio.Event().wait()
		finally:
			cancelled.set()

	class BlockingClient:
		def __init__(self, *args, **kwargs):
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			return None

		post = block

	monkeypatch.setattr("flow_harness.agent.client_tools.httpx.AsyncClient", BlockingClient)
	(tmp_path / "a.txt").write_text("secret")
	report = AssistantMessage(content=[ToolCall(id="c1", name="report", arguments={})])
	cases = [
		("before hook", {}, _read_call(), {"before_tool_call": block}),
		("after hook", {}, _read_call(), {"after_tool_call": block}),
		("client callback", _REPORT_CLIENT, report, {}),
	]
	for name, config, reply, hooks in cases:
		started.clear()
		cancelled.clear()
		session, events = _session(tmp_path, **config)
		handle = await session.run("go", model=MockModel(replies=[reply]), **hooks)
		await started.wait()
		session.abort()
		assert handle.task is not None
		await asyncio.wait_for(handle.task, timeout=1)

		assert cancelled.is_set(), name
		assert [r["details"].get("repair") for r in _of(events, "tool_result")] == ["interrupted"], name
		assert _of(events, "run_ended")[-1]["reason"] == "aborted", name


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


async def test_concurrent_tools_run_together_and_other_tools_alone(tmp_path, monkeypatch):
	timeline: list[str] = []
	both_running = asyncio.Event()

	@tool(concurrent=True)
	async def pair(name: str, *, ctx) -> RuntimeToolResult:
		timeline.append(f"start {name}")
		if len([t for t in timeline if t.startswith("start")]) == 2:
			both_running.set()
		await asyncio.wait_for(both_running.wait(), 5)  # hangs if the pair ran one after the other
		timeline.append(f"end {name}")
		return RuntimeToolResult(content=name)

	@tool
	async def solo(*, ctx) -> RuntimeToolResult:
		timeline.append("solo")
		return RuntimeToolResult(content="solo")

	def before(call, ctx):
		timeline.append(f"hook {call.args.get('name', call.name)}")

	monkeypatch.setitem(BUILTIN_TOOLS, "pair", pair)
	monkeypatch.setitem(BUILTIN_TOOLS, "solo", solo)
	session, _ = _session(tmp_path, tools=["pair", "solo"], auto_approve=True)
	model = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="pair", arguments={"name": "a"}),
					ToolCall(id="c2", name="pair", arguments={"name": "b"}),
					ToolCall(id="c3", name="solo", arguments={}),
				]
			),
			AssistantMessage(content="done"),
		]
	)

	await _run(session, "go", model=model, before_tool_call=before)

	# the pair is held while its second member passes the hooks, then runs together
	assert timeline[:4] == ["hook a", "hook b", "start a", "start b"]
	# the held pair ran before the next call's hook looked
	assert timeline[-2:] == ["hook solo", "solo"]
	# results reach the model in call order however the pair finished
	assert [m.tool_call_id for m in session.transcript.messages if m.type == "tool_result"] == [
		"c1",
		"c2",
		"c3",
	]


async def test_client_tool_round_trips_the_callback_and_unwraps_the_frappe_envelope(tmp_path, monkeypatch):
	seen = {}

	class RecordingClient:
		def __init__(self, *args, timeout, **kwargs):
			seen["timeout"] = timeout

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

	monkeypatch.setattr("flow_harness.agent.client_tools.httpx.AsyncClient", RecordingClient)
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
		callback_headers={"X-Site": "alpha", "x-harness-token": "stale"},
		callback_timeout=7,
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
	assert seen["headers"].get_list("x-harness-token") == ["shared-secret"]
	assert seen["headers"]["X-Site"] == "alpha"
	assert seen["timeout"] == 7
	assert seen["payload"].pop("result_token")
	assert seen["payload"] == {
		"callback_type": "tool",
		"session_id": session.id,
		"tool": "check_mail",
		"args": {},
		"user_context": {"user": "alice"},
		"mode": "execute",
	}
	results = _of(events, "tool_result")
	assert [r["content"] for r in results] == ["42 unread emails"]  # envelope unwrapped
	assert _of(events, "run_ended")[-1]["reason"] == "done"


_REPORT_CLIENT = {
	"tools": [],
	"client_tools": [
		{
			"type": "function",
			"function": {
				"name": "report",
				"description": "build",
				"parameters": {"type": "object", "properties": {}},
			},
		}
	],
	"callback_url": "https://client.invalid/tools",
	"auto_approve": True,
}


def _report_model():
	return MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="report", arguments={})]),
			AssistantMessage(content="done"),
		]
	)


async def test_a_pending_client_tool_waits_for_its_posted_result(tmp_path, monkeypatch):
	called = asyncio.Event()
	seen = {}

	async def post(config, url, payload):
		seen.update(payload)
		called.set()
		if early is not None:
			assert deliver_result(payload["session_id"], payload["result_token"], early)
		return {"pending": True, "timeout": timeout}

	monkeypatch.setattr("flow_harness.agent.client_tools._post", post)

	# a result posted before the callback answers is taken
	early, timeout = {"content": "report ready"}, 5
	session, events = _session(tmp_path, **_REPORT_CLIENT)
	await _run(session, "build the report", model=_report_model())
	assert [r["content"] for r in _of(events, "tool_result")] == ["report ready"]

	# no result in time is an error
	early, timeout = None, 0.01
	session, events = _session(tmp_path, **_REPORT_CLIENT)
	await _run(session, "build the report", model=_report_model())
	[result] = _of(events, "tool_result")
	assert result["is_error"]
	assert result["content"] == "[tool error: background tool 'report' sent no result in time]"

	# an abort stops the wait, and a late result finds nothing waiting
	timeout = 60
	called.clear()
	session, events = _session(tmp_path, **_REPORT_CLIENT)
	handle = await session.run("build the report", model=_report_model())
	await called.wait()
	session.abort()
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=1)
	assert _of(events, "run_ended")[-1]["reason"] == "aborted"
	assert not deliver_result(session.id, seen["result_token"], {"content": "late"})


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


BIG = "x" * 100_000  # ~25k estimated tokens: past any test threshold, over the kept tail


class _OverflowModel(Model):
	"""Call 1 overflows; call 2 serves the summarizer; call 3 answers, or overflows again."""

	name = "overflow"

	def __init__(self, *, overflow_again: bool):
		self.overflow_again = overflow_again
		self.calls = 0
		self.summarizer_prompt_chars = 0

	async def run(self, request: ModelRequest):
		self.calls += 1
		if self.calls == 2:
			self.summarizer_prompt_chars = len(request.messages[0].content)
			yield AssistantMessage(content="## Goal\noverflow summary")
		elif self.calls == 1 or self.overflow_again:
			raise ProviderError(
				kind="context_overflow",
				retryable=False,
				status_code=400,
				provider="test",
				detail="prompt is too long",
			)
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

	# the summarizer's spend counts toward the run budget
	session, events = _session(tmp_path, compact_threshold_tokens=100, token_budget=5)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first answer")]))

	mock = MockModel(replies=[AssistantMessage(content="## Goal\ncompacted summary"), _read_call()])
	await _run(session, "continue", model=mock)

	assert mock._turn == 1  # the summarizer used the remaining budget
	assert _of(events, "run_ended")[-1]["reason"] == "budget"


async def test_a_threshold_compaction_that_fails_or_is_aborted_folds_nothing(tmp_path):
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
	assert _of(events, "run_ended")[-1]["reason"] == "done"  # the failure keeps the turn
	assert len(session.transcript.messages) == 4  # nothing was folded
	assert session.transcript.messages[-1].text == "still answered"

	class BlockingSummarizer(MockModel):
		def __init__(self):
			super().__init__()
			self.started = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await asyncio.Event().wait()
			yield AssistantMessage(content="never")

	session, events = _session(tmp_path, compact_threshold_tokens=100)
	await _run(session, BIG, model=MockModel(replies=[AssistantMessage(content="first")]))
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


async def test_overflow_compacts_once_and_retries_the_turn(tmp_path):
	async def overflow_after_a_giant_message(overflow_again):
		# a message so large it overflowed on its own; the summarizer input must be
		# clipped and budgeted or the recovery call would overflow too
		session, events = _session(tmp_path, compact_threshold_tokens=1_000_000_000)
		giant = "y" * 600_000  # ~150k estimated tokens, over the 128k default window
		await _run(session, giant, model=MockModel(replies=[AssistantMessage(content="first")]))
		model = _OverflowModel(overflow_again=overflow_again)
		await _run(session, "continue", model=model)

		assert model.calls == 3  # original, summarizer, retry — no second recovery
		assert 0 < model.summarizer_prompt_chars < 60_000  # the 600k message was clipped
		assert [row["reason"] for row in _of(events, "compaction")] == ["overflow"]  # the recovery is durable
		assert session.transcript.messages[0].content.startswith("Previous conversation summary:")
		return session, events

	session, events = await overflow_after_a_giant_message(overflow_again=False)
	assert _of(events, "run_error") == []
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	assert session.transcript.messages[-1].text == "recovered"

	# a second overflow in the same run fails typed
	session, events = await overflow_after_a_giant_message(overflow_again=True)
	assert _of(events, "run_error")[-1]["kind"] == "context_overflow"
	assert _of(events, "run_ended")[-1]["reason"] == "error"


async def test_auto_compact_disabled_turns_both_paths_off(tmp_path):
	class TrackingModel(MockModel):
		def __init__(self):
			super().__init__(replies=[AssistantMessage(content="one"), AssistantMessage(content="two")])
			self.limit_loads = 0

		async def load_model_limits(self, cancellation=None):
			self.limit_loads += 1

	session, events = _session(tmp_path, auto_compact=False, compact_threshold_tokens=10)
	model = TrackingModel()
	await _run(session, BIG, model=model)
	await _run(session, "again", model=model)
	assert _of(events, "compaction_started") == []
	assert model.limit_loads == 0

	failing = _FailingModel(
		ProviderError(kind="context_overflow", retryable=False, status_code=400, provider="test", detail="x")
	)
	await _run(session, "boom", model=failing)

	assert failing.attempts == 1  # no compact-and-retry
	assert _of(events, "run_error")[-1]["kind"] == "context_overflow"


async def test_a_small_window_compacts_only_past_its_threshold_keeping_a_scaled_tail(tmp_path):
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
	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 0)
	session, events = _session(tmp_path, tools=["count_once"], auto_approve=True)

	await _run(session, "go", model=ToolThenFlakyModel())

	assert tool_runs == 1
	assert [event["tool_call_id"] for event in _of(events, "tool_result")] == ["count-1"]
	assert [event["status"] for event in _of(events, "retry")] == ["scheduled", "started"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
