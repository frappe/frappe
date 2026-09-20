"""The subagent builtin end to end: a child run inside the session, its rows tagged in
the session's log, named agents, parallel children under the cap, and how a child's end
reaches the model."""

import asyncio
import shutil
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from flow_harness.agent.agent import Agent
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
from flow_harness.tools import ToolContext, ToolResult, select_tools, tool
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
	assert result["content"] == "forty-two beans\n\n[subagent_id: c1]"
	assert result["is_error"] is False
	assert result["details"]["end_reason"] == "done" and result["details"]["subagent_id"] == "c1"
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
	assert result["content"] == "found\n\n[subagent_id: c1]" and result["details"]["agent"] == "Lookup"


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


async def test_a_child_has_no_runner_so_nothing_inside_it_can_delegate(tmp_path):
	@tool
	async def delegate(*, ctx: ToolContext) -> ToolResult:
		return ToolResult(content="runner: " + ("absent" if ctx.run_subagent is None else "present"))

	session, events = _session(tmp_path)
	assert session.server_tools is not None
	session.server_tools["delegate"] = (
		delegate  # what an extension tool would be, in the session and its children
	)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[ToolCall(id="p1", name="delegate", arguments={})]),
				AssistantMessage(content=[_spawn("c1", "try it")]),
				AssistantMessage(content="done"),
			],
			"try it": [
				AssistantMessage(content=[ToolCall(id="c2", name="delegate", arguments={})]),
				AssistantMessage(content="tried"),
			],
		}
	)

	await _run(session, "go", model)

	assert _of(events, "tool_result")[0]["content"] == "runner: present"
	assert _of(events, "tool_result", subagent="c1")[0]["content"] == "runner: absent"
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1"}


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

	assert {r["tool_call_id"]: r["content"] for r in _of(events, "tool_result")} == {
		"c1": "L\n\n[subagent_id: c1]",
		"c2": "R\n\n[subagent_id: c2]",
	}
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
	assert _of(events, "tool_result")[0]["content"] == "ran it\n\n[subagent_id: c1]"
	assert _of(events, "run_ended")[-1]["reason"] == "done"


@pytest.mark.parametrize("initial_auto_approve", [True, False])
async def test_an_approval_mode_change_reaches_a_running_childs_next_gate(tmp_path, initial_auto_approve):
	session, events = _session(tmp_path, auto_approve=initial_auto_approve)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="ran it")],
		}
	)
	gate = model.gate("risky")

	handle = await session.run("go", model=model)
	await model.started["risky"].wait()  # the child is running, its tool call still to come
	session.config.auto_approve = not initial_auto_approve  # PATCH /config mutates this object
	gate.set()

	if initial_auto_approve:
		await _until(lambda: _of(events, "approval_required", subagent="c1"))
		approval = _of(events, "approval_required", subagent="c1")[0]
		await session.resume({"c2": "Approve"}, approval_seq=approval["seq"])
	assert handle.task is not None
	await asyncio.wait_for(handle.task, timeout=5)
	assert bool(_of(events, "approval_required", subagent="c1")) is initial_auto_approve
	assert _of(events, "tool_result")[0]["content"] == "ran it\n\n[subagent_id: c1]"


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


async def test_the_agent_facade_answers_a_child_batch_and_streams_the_whole_run(tmp_path):
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="ran it")],
		}
	)
	agent = Agent(model=model, data_dir=str(tmp_path / "data"), cwd=str(tmp_path))
	seen = []

	async def stream():
		async for event in agent.run("go"):
			seen.append(event)

	run = asyncio.create_task(stream())
	await _until(lambda: any(e.type == "run_ended" and e.subagent_id == "c1" for e in seen))
	approval = next(e for e in seen if e.type == "approval_required")
	assert [e async for e in agent.resume({"c2": "Approve"}, approval_seq=approval.seq)] == []
	await run

	assert [e.reason for e in seen if e.type == "run_ended" and e.subagent_id == "c1"] == ["paused", "done"]
	assert [e.reason for e in seen if e.type == "run_ended" and e.subagent_id is None] == ["done"]
	assert seen[-1].type == "run_ended" and seen[-1].subagent_id is None


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


async def test_continuing_a_child_keeps_its_context_and_agent_even_after_a_reload(tmp_path):
	agents = [SubagentConfig(name="Counter", description="counts", system_prompt="you count")]
	session, events = _session(tmp_path, subagents=agents)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "first", agent="Counter")]),
				AssistantMessage(content=[_spawn("c9", "second", subagent_id="c1")]),
				AssistantMessage(content="done"),
			],
			"first": [AssistantMessage(content="one")],
			"second": [AssistantMessage(content="two")],
			"again": [
				AssistantMessage(content=[_spawn("c20", "third", subagent_id="c1")]),
				AssistantMessage(content="done"),
			],
			"third": [AssistantMessage(content="three")],
		}
	)

	await _run(session, "go", model)

	second = next(r for r in model.requests if _last_user(r.messages) == "second")
	assert [m.text for m in second.messages if m.type == "user_message"] == ["first", "second"]
	assert second.system_prompt == "you count"
	result = _of(events, "tool_result")[1]
	assert result["content"] == "two\n\n[subagent_id: c1]" and result["details"]["agent"] == "Counter"
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1"}  # one child, two runs

	reloaded = SessionStore(str(tmp_path / "data"), event_sink=lambda _sid, ev: events.append(ev)).get(
		session.id
	)
	await _run(reloaded, "again", model)

	third = next(r for r in model.requests if _last_user(r.messages) == "third")
	assert [m.text for m in third.messages if m.type == "user_message"] == ["first", "second", "third"]
	assert third.system_prompt == "you count"
	assert _of(events, "tool_result")[-1]["content"] == "three\n\n[subagent_id: c1]"
	assert [m.type for m in Transcript.replay(reloaded.log, subagent_id="c1").messages] == [
		"user_message",
		"assistant_message",
	] * 3


async def test_a_continuation_is_refused_for_a_running_child_an_unknown_id_or_with_an_agent(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(
					content=[
						_spawn("c1", "slow"),
						_spawn("c2", "more", subagent_id="c1"),
						_spawn("c3", "more", subagent_id="nope"),
						_spawn("c4", "more", agent="general", subagent_id="c1"),
					]
				),
				AssistantMessage(content="done"),
			],
			"slow": [AssistantMessage(content="late")],
		}
	)
	model.gate("slow")

	handle = await session.run("go", model=model)
	await model.started["slow"].wait()
	model.gates["slow"].set()
	assert handle.task is not None
	await handle.task

	results = {r["tool_call_id"]: r for r in _of(events, "tool_result")}
	assert results["c1"]["content"] == "late\n\n[subagent_id: c1]" and not results["c1"]["is_error"]
	assert results["c2"]["content"] == "[sub-agent 'c1' is still running]"
	assert results["c3"]["content"] == "[unknown subagent_id 'nope']"
	assert results["c4"]["content"] == "[pass either agent or subagent_id, not both]"
	assert all(results[cid]["is_error"] for cid in ("c2", "c3", "c4"))


@pytest.mark.parametrize("how", ["abort", "restart"])
async def test_a_continued_child_has_what_an_abort_or_a_crash_left_open_closed_first(tmp_path, how):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "first")]), AssistantMessage(content="done")],
			"first": [AssistantMessage(content="one")],
			"more": [AssistantMessage(content=[_spawn("c2", "second", subagent_id="c1")])],
			"second": [AssistantMessage(content=[_bash("c9")])],
			"again": [
				AssistantMessage(content=[_spawn("c3", "third", subagent_id="c1")]),
				AssistantMessage(content="done"),
			],
			"third": [AssistantMessage(content="three")],
		}
	)

	await _run(session, "go", model)
	handle = await session.run("more", model=model)
	await _until(lambda: [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["done", "paused"])
	assert handle.task is not None
	if how == "abort":
		assert session.abort() is True
		await handle.task
		continued = session
	else:  # the log as a crash leaves it, opened by a fresh process
		shutil.copytree(tmp_path / "data", tmp_path / "restarted")
		continued = SessionStore(
			str(tmp_path / "restarted"), event_sink=lambda _sid, ev: events.append(ev)
		).get(session.id)
	await _run(continued, "again", model)

	third = next(r for r in model.requests if _last_user(r.messages) == "third")
	assert [m.type for m in third.messages] == ["user_message", "assistant_message"] * 2 + [
		"tool_result",
		"user_message",
	]
	closed = third.messages[4]
	assert (
		closed.tool_call_id == "c9" and ("interrupted" if how == "abort" else "cancelled") in closed.content
	)
	assert _of(events, "tool_result")[-1]["content"] == "three\n\n[subagent_id: c1]"
	if how == "restart":  # the paused session's own run is still parked in this process
		session.abort()
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
