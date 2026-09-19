"""The subagent builtin end to end: a child run inside the session, its rows tagged in
the session's log, named agents, parallel children under the cap, and how a child's end
reaches the model."""

import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from flow_harness.agent.loop import HookDecision, LoopInputs
from flow_harness.events import AssistantMessage, ToolCall
from flow_harness.model import ProviderError
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.mock import MockModel, _last_user
from flow_harness.server import create_app
from flow_harness.server.policy import ServerPolicy
from flow_harness.server.routes.sessions import _summary
from flow_harness.session.config import SessionConfig, SubagentConfig
from flow_harness.session.session import ResumeError, SessionConflict
from flow_harness.session.store import PolicyError, SessionStore
from flow_harness.session.subagents import _child_inputs
from flow_harness.session.transcript import Transcript
from flow_harness.tools import select_tools
from flow_harness.tools.builtins.subagent import subagent


class ScriptedModel(MockModel):
	"""One model for the session and its children: replies come from the script keyed by
	the last user message, in order; a keyed gate holds that turn until the test opens it."""

	def __init__(
		self, scripts: dict[str, list[AssistantMessage]], *, errors: dict[str, Exception] | None = None
	):
		super().__init__(replies=[])
		self.scripts = {key: list(replies) for key, replies in scripts.items()}
		self.errors = errors or {}
		self.gates: dict[str, asyncio.Event] = {}
		self.started: dict[str, asyncio.Event] = {}
		self.requests = []

	def gate(self, key: str) -> asyncio.Event:
		self.started.setdefault(key, asyncio.Event())
		return self.gates.setdefault(key, asyncio.Event())

	async def run(self, request):
		self.requests.append(
			replace(request, messages=list(request.messages))
		)  # a snapshot: the list is live
		key = _last_user(request.messages)
		if key in self.errors:
			raise self.errors[key]
		if key in self.gates:
			self.started[key].set()
			await self.gates[key].wait()
		async for event in super().run(request):
			yield event

	def _next_reply(self, messages):
		replies = self.scripts.get(_last_user(messages), [])
		return replies.pop(0) if replies else AssistantMessage()


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path / "data"), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path), **cfg))
	return session, events


async def _run(session, message, model, **kwargs):
	handle = await session.run(message, model=model, **kwargs)
	assert handle.task is not None
	await handle.task


def _of(events, kind, subagent=None):
	return [e for e in events if e["type"] == kind and e.get("subagent_id") == subagent]


def _spawn(cid, task, **args):
	return ToolCall(id=cid, name="subagent", arguments={"task": task, "description": "a task", **args})


def _bash(cid):
	return ToolCall(id=cid, name="bash", arguments={"command": "true"})


async def _until(check):
	async with asyncio.timeout(5):
		while not check():
			await asyncio.sleep(0.01)


async def test_a_subagent_answers_from_a_fresh_context(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "count the beans")]),
				AssistantMessage(content="done"),
			],
			"count the beans": [AssistantMessage(content="forty-two beans")],
		}
	)

	await _run(session, "go", model)

	# the child saw only its task, with the session's prompt and tools minus subagent
	child = next(r for r in model.requests if _last_user(r.messages) == "count the beans")
	assert [m.type for m in child.messages] == ["user_message"]
	assert session.config.system_prompt is not None
	assert child.system_prompt == session.config.system_prompt.replace(
		f"\n- subagent: {subagent.prompt_snippet}", ""
	)
	assert "- subagent: " in session.config.system_prompt and "- subagent: " not in child.system_prompt
	assert "subagent" not in [t["function"]["name"] for t in child.tools]
	# the parent got the answer and nothing of the child's steps
	result = _of(events, "tool_result")[0]
	assert result["content"] == "forty-two beans"
	assert result["is_error"] is False
	assert result["details"]["end_reason"] == "done"
	# the child's rows share the log under the call id and stay out of the session's transcript
	durable = [e for e in events if e.get("subagent_id") == "c1" and "seq" in e and e["type"] != "usage"]
	assert [e["type"] for e in durable] == ["run_started", "user_message", "assistant_message", "run_ended"]
	assert [m.type for m in session.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"assistant_message",
	]
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_the_tool_stays_bound_when_the_session_tools_are_recomposed(tmp_path):
	events: list[dict] = []
	store = SessionStore(str(tmp_path / "data"), event_sink=lambda _sid, ev: events.append(ev))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	session.server_tools = store.resolve_tools(
		session.config
	)  # what a config patch or an extension reload does
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "count")]), AssistantMessage(content="done")],
			"count": [AssistantMessage(content="three")],
		}
	)

	await _run(session, "go", model)

	assert _of(events, "tool_result")[0]["content"] == "three"


async def test_an_extension_tool_named_subagent_is_left_alone(tmp_path):
	session, events = _session(tmp_path)
	assert session.server_tools is not None
	session.server_tools["subagent"] = replace(subagent, description="an extension's own")
	model = ScriptedModel(
		{"go": [AssistantMessage(content=[_spawn("c1", "x")]), AssistantMessage(content="done")]}
	)

	await _run(session, "go", model)

	# the extension's tool ran as it is; nothing was bound over it and no child started
	assert "not available" in _of(events, "tool_result")[0]["content"]
	assert not [e for e in events if e.get("subagent_id")]


async def test_a_named_agent_runs_with_its_own_prompt_and_tools(tmp_path):
	agents = [
		SubagentConfig(
			name="Lookup", description="finds things", system_prompt="you look things up", tools=["read"]
		)
	]
	session, events = _session(tmp_path, subagents=agents)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "find it", agent="Lookup")]),
				AssistantMessage(content="done"),
			],
			"find it": [AssistantMessage(content="found")],
		}
	)

	await _run(session, "go", model)

	parent, child = model.requests[0], model.requests[1]
	description = next(
		t["function"]["description"] for t in parent.tools if t["function"]["name"] == "subagent"
	)
	assert description.endswith(
		"Available agents:\n- general: a copy of you with a fresh context\n- Lookup: finds things"
	)
	assert child.system_prompt == "you look things up"
	assert [t["function"]["name"] for t in child.tools] == ["read"]
	result = _of(events, "tool_result")[0]
	assert result["content"] == "found" and result["details"]["agent"] == "Lookup"


async def test_a_named_agent_runs_at_its_own_effort(tmp_path):
	careful = SubagentConfig(name="Careful", reasoning_effort="low")
	session, _ = _session(tmp_path, reasoning_effort="high", subagents=[careful])
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "think", agent="Careful")]),
				AssistantMessage(content="done"),
			],
			"think": [AssistantMessage(content="thought")],
		}
	)

	await _run(session, "go", model)

	parent, child = model.requests[0], model.requests[1]
	assert (parent.params["reasoning_effort"], child.params["reasoning_effort"]) == ("high", "low")


async def test_an_unknown_agent_is_an_error_result(tmp_path):
	session, events = _session(tmp_path, subagents=[SubagentConfig(name="Lookup")])
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "x", agent="Nobody")]),
				AssistantMessage(content="done"),
			]
		}
	)

	await _run(session, "go", model)

	result = _of(events, "tool_result")[0]
	assert result["is_error"] and result["content"] == "[unknown agent 'Nobody'; available: general, Lookup]"
	assert not [e for e in events if e.get("subagent_id")]


def test_a_child_takes_credentials_with_its_model_or_on_their_own(tmp_path):
	config = SessionConfig(cwd=str(tmp_path), api_key="parent-key", api_base="http://parent")
	inputs = LoopInputs(
		config=config,
		messages=[],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
		abort=asyncio.Event(),
		model_name="mock",
		credential_id="cred",
		model=MockModel(replies=[]),
	)

	def child(**definition):
		agent = SubagentConfig(name="a", **definition)
		return _child_inputs(inputs, Transcript("c1"), agent, lambda config: select_tools(config.tools))

	def selection(child_inputs):
		return (
			child_inputs.model,
			child_inputs.model_name,
			child_inputs.credential_id,
			child_inputs.config.api_key,
			child_inputs.config.api_base,
		)

	assert selection(child()) == (inputs.model, "mock", "cred", "parent-key", "http://parent")
	assert selection(child(api_key="child-key")) == (None, "mock", None, "child-key", None)
	assert selection(child(model="other")) == (None, "other", None, None, None)
	assert child().reasoning_effort is None and child(reasoning_effort="low").reasoning_effort == "low"


def test_config_checks_agent_names_and_redacts_their_keys():
	with pytest.raises(ValidationError, match="reserved"):
		SessionConfig(subagents=[SubagentConfig(name="general")])
	with pytest.raises(ValidationError, match="unique"):
		SessionConfig(subagents=[SubagentConfig(name="a"), SubagentConfig(name="a")])
	config = SessionConfig(subagents=[SubagentConfig(name="a", api_key="sk-secret")])
	assert config.redacted()["subagents"][0]["api_key"] == "***"


def test_an_agents_tools_must_pass_the_allowlist(tmp_path):
	store = SessionStore(str(tmp_path / "data"), tool_allowlist={"read", "subagent"})
	config = SessionConfig(cwd=str(tmp_path), subagents=[SubagentConfig(name="a", tools=["bash", "read"])])
	with pytest.raises(PolicyError, match="bash"):
		store.create(config)


def test_the_api_refuses_agent_credentials_like_the_sessions_and_redacts_them(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	agents = [{"name": "Lookup", "description": "finds things", "model": "mock", "api_key": "sk-secret"}]
	body = {"cwd": str(tmp_path), "subagents": agents}
	assert TestClient(create_app(store)).post("/sessions", json=body).status_code == 400
	client = TestClient(create_app(store, policy=ServerPolicy(inline_credentials=True)))
	created = client.post("/sessions", json=body)
	assert created.status_code == 200
	echoed = client.get(f"/sessions/{created.json()['session_id']}").json()["config"]["subagents"][0]
	assert echoed["api_key"] == "***" and echoed["model"] == "mock"
	reserved = {"cwd": str(tmp_path), "subagents": [{"name": "general"}]}
	assert client.post("/sessions", json=reserved).status_code == 422


async def test_a_subagent_cannot_start_subagents(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "delegate")]), AssistantMessage(content="done")],
			"delegate": [
				AssistantMessage(content=[_spawn("c2", "deeper")]),
				AssistantMessage(content="gave up"),
			],
		}
	)

	await _run(session, "go", model)

	nested = _of(events, "tool_result", subagent="c1")[0]
	assert nested["tool_call_id"] == "c2" and nested["is_error"]
	assert "unknown tool: subagent" in nested["content"]
	assert "gave up" in _of(events, "tool_result")[0]["content"]


async def test_subagents_called_in_one_turn_run_together(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "left"), _spawn("c2", "right")]),
				AssistantMessage(content="done"),
			],
			"left": [AssistantMessage(content="L")],
			"right": [AssistantMessage(content="R")],
		}
	)
	model.gate("left")
	model.gate("right")

	handle = await session.run("go", model=model)
	# both children are inside their model turn at once
	await asyncio.wait_for(asyncio.gather(model.started["left"].wait(), model.started["right"].wait()), 5)
	model.gates["left"].set()
	model.gates["right"].set()
	assert handle.task is not None
	await handle.task

	assert {r["tool_call_id"]: r["content"] for r in _of(events, "tool_result")} == {"c1": "L", "c2": "R"}
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1", "c2"}


async def test_the_cap_holds_back_extra_subagents(tmp_path):
	session, events = _session(tmp_path, max_concurrent_subagents=1)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "first"), _spawn("c2", "second")]),
				AssistantMessage(content="done"),
			],
			"first": [AssistantMessage(content="1")],
			"second": [AssistantMessage(content="2")],
		}
	)
	model.gate("first")
	model.gate("second")

	handle = await session.run("go", model=model)
	await model.started["first"].wait()
	await asyncio.sleep(0.05)
	assert not model.started["second"].is_set()
	model.gates["first"].set()
	await model.started["second"].wait()
	model.gates["second"].set()
	assert handle.task is not None
	await handle.task

	assert len(_of(events, "tool_result")) == 2


async def test_abort_stops_a_running_child(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel({"go": [AssistantMessage(content=[_spawn("c1", "slow")])]})
	model.gate("slow")

	handle = await session.run("go", model=model)
	await model.started["slow"].wait()
	assert session.abort() is True
	assert handle.task is not None
	await handle.task

	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "aborted"
	assert _of(events, "run_ended")[0]["reason"] == "aborted"
	assert session.state == "idle"


async def test_abort_releases_a_child_still_waiting_for_a_slot(tmp_path):
	session, events = _session(tmp_path, max_concurrent_subagents=1)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "first"), _spawn("c2", "second")])],
			"first": [AssistantMessage(content="1")],
			"second": [AssistantMessage(content="2")],
		}
	)
	model.gate("first")

	handle = await session.run("go", model=model)
	await model.started["first"].wait()
	await asyncio.sleep(0.05)
	assert session.abort() is True
	assert handle.task is not None
	await handle.task

	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "aborted"
	assert _of(events, "run_ended", subagent="c2") == []  # never started, so nothing to settle
	assert {r["tool_call_id"] for r in _of(events, "tool_result")} == {"c1", "c2"}
	assert _of(events, "run_ended")[0]["reason"] == "aborted"


async def test_a_failing_child_is_an_error_result_and_the_session_carries_on(tmp_path):
	session, events = _session(tmp_path)
	error = ProviderError(kind="auth", retryable=False, status_code=401, provider="mock", detail="bad key")
	model = ScriptedModel(
		{"go": [AssistantMessage(content=[_spawn("c1", "boom")]), AssistantMessage(content="done")]},
		errors={"boom": error},
	)

	await _run(session, "go", model)

	assert _of(events, "run_error", subagent="c1")[0]["kind"] == "auth"
	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "error"
	result = _of(events, "tool_result")[0]
	assert result["is_error"] and "[sub-agent stopped: error: ProviderError:" in result["content"]
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_a_child_approval_pauses_only_the_child_and_resume_reaches_it(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="ran it")],
		}
	)

	handle = await session.run("go", model=model)
	await _until(lambda: _of(events, "run_ended", subagent="c1"))

	approval = _of(events, "approval_required", subagent="c1")[0]
	assert [call["id"] for call in approval["calls"]] == ["c2"]
	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "paused"
	assert session.state == "running" and session.transcript.pending_approval is None
	with pytest.raises(ResumeError):
		await session.resume({"c9": "Approve"}, approval_seq=approval["seq"])

	resumed = await session.resume({"c2": "Approve"}, approval_seq=approval["seq"])
	assert resumed.status == "resumed" and resumed.task is None
	assert handle.task is not None
	await handle.task

	ran = _of(events, "tool_result", subagent="c1")[0]
	assert ran["tool_call_id"] == "c2" and not ran["is_error"]
	assert [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["paused", "done"]
	assert _of(events, "tool_result")[0]["content"] == "ran it"
	assert _of(events, "run_ended")[-1]["reason"] == "done"


@pytest.mark.parametrize("how", ["deny", "cancel"])
async def test_a_denied_or_cancelled_child_is_an_error_result(tmp_path, how):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="never reached")],
		}
	)

	handle = await session.run("go", model=model)
	await _until(lambda: _of(events, "run_ended", subagent="c1"))
	if how == "deny":
		seq = _of(events, "approval_required", subagent="c1")[0]["seq"]
		await session.resume({"c2": "Deny"}, approval_seq=seq)
	else:
		assert await session.cancel_pending() is True
	assert handle.task is not None
	await handle.task

	stopped = "denied" if how == "deny" else "cancelled"
	child = _of(events, "tool_result", subagent="c1")[0]
	assert child["tool_call_id"] == "c2" and child["is_error"] and stopped in child["content"]
	result = _of(events, "tool_result")[0]
	assert result["is_error"] and f"[sub-agent stopped: {stopped}]" in result["content"]
	assert session.state == "idle" and _of(events, "run_ended")[-1]["reason"] == "done"


async def test_a_batch_answered_twice_is_refused_the_second_time(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="ran it")],
		}
	)

	handle = await session.run("go", model=model)
	await _until(lambda: _of(events, "run_ended", subagent="c1"))
	seq = _of(events, "approval_required", subagent="c1")[0]["seq"]
	await session.resume({"c2": "Approve"}, approval_seq=seq)
	with pytest.raises(SessionConflict):  # answered, but the child has not woken yet
		await session.resume({"c2": "Approve"}, approval_seq=seq)
	with pytest.raises(SessionConflict):
		await session.cancel_pending()
	assert handle.task is not None
	await handle.task

	assert [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["paused", "done"]


async def test_abort_ends_a_child_waiting_for_approval(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")])],
			"risky": [AssistantMessage(content=[_bash("c2")])],
		}
	)

	handle = await session.run("go", model=model)
	await _until(lambda: _of(events, "run_ended", subagent="c1"))
	assert session.abort() is True
	assert handle.task is not None
	await handle.task

	assert [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["paused", "aborted"]
	assert _of(events, "run_ended")[0]["reason"] == "aborted" and session.state == "idle"


async def test_answers_and_cancellation_are_refused_while_no_child_waits(tmp_path):
	session, _ = _session(tmp_path)
	model = ScriptedModel(
		{"go": [AssistantMessage(content=[_spawn("c1", "slow")])], "slow": [AssistantMessage()]}
	)
	model.gate("slow")

	handle = await session.run("go", model=model)
	await model.started["slow"].wait()
	with pytest.raises(SessionConflict):
		await session.resume({"c2": "Approve"}, approval_seq=99)
	with pytest.raises(SessionConflict):
		await session.cancel_pending()
	model.gates["slow"].set()
	assert handle.task is not None
	await handle.task


async def test_the_run_hooks_reach_the_child(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "look")]), AssistantMessage(content="done")],
			"look": [
				AssistantMessage(content=[ToolCall(id="c2", name="read", arguments={"path": "a.txt"})]),
				AssistantMessage(content="seen"),
			],
		}
	)
	seen: list[str] = []

	def before(call, ctx):
		seen.append(call.name)
		return HookDecision(result="not for you", is_error=True) if call.name == "read" else None

	await _run(session, "go", model, before_tool_call=before)

	assert seen == ["subagent", "read"]
	assert _of(events, "tool_result", subagent="c1")[0]["content"] == "not for you"


async def test_the_wait_summary_reports_the_session_answer_with_the_child_usage(tmp_path):
	session, _ = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "work")]), AssistantMessage(content="the answer")],
			"work": [AssistantMessage(content="child text that is not the answer")],
		}
	)

	await _run(session, "go", model)

	summary = _summary(session, 0)
	assert summary["output"] == "the answer"
	assert summary["reason"] == "done"
	child_usage = sum(e["output_tokens"] for e in _of(session.log.read_since(0), "usage", subagent="c1"))
	assert child_usage > 0
	assert summary["usage"]["output_tokens"] > child_usage
