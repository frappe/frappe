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
from flow_harness.agent.loop import HookDecision, LoopInputs, TokenBudget
from flow_harness.events import AssistantMessage, ToolCall, Usage
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
			"count the beans": [
				AssistantMessage(content=[ToolCall(id="c2", name="read", arguments={"path": "a.txt"})]),
				AssistantMessage(content="forty-two beans"),
			],
		}
	)
	seen: list[str] = []

	def before(call, ctx):
		seen.append(call.name)
		return HookDecision(result="not for you", is_error=True) if call.name == "read" else None

	await _run(session, "go", model, before_tool_call=before)

	# the child saw only its task, with the session's prompt and tools minus subagent
	child = next(r for r in model.requests if _last_user(r.messages) == "count the beans")
	assert [m.type for m in child.messages] == ["user_message"]
	assert session.config.system_prompt is not None
	assert child.system_prompt == session.config.system_prompt.replace(
		f"\n- subagent: {subagent.prompt_snippet}", ""
	)
	assert "- subagent: " in session.config.system_prompt and "- subagent: " not in child.system_prompt
	assert "subagent" not in [t["function"]["name"] for t in child.tools]
	# the run's hooks reach the child
	assert seen == ["subagent", "read"]
	assert _of(events, "tool_result", subagent="c1")[0]["content"] == "not for you"
	# the parent got the answer and nothing of the child's steps
	result = _of(events, "tool_result")[0]
	assert result["content"] == "forty-two beans\n\n[subagent_id: c1]"
	assert result["is_error"] is False
	assert result["details"]["end_reason"] == "done" and result["details"]["subagent_id"] == "c1"
	# the child's rows share the log under the call id and stay out of the session's transcript
	durable = [e for e in events if e.get("subagent_id") == "c1" and "seq" in e and e["type"] != "usage"]
	assert [e["type"] for e in durable] == [
		"run_started",
		"user_message",
		"assistant_message",
		"tool_result",
		"assistant_message",
		"run_ended",
	]
	assert [m.type for m in session.transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"assistant_message",
	]
	assert _of(events, "run_ended")[-1]["reason"] == "done"
	# the wait summary reports the session's answer, with the child's usage counted in
	summary = _summary(session, 0)
	assert summary["output"] == "done"
	assert summary["reason"] == "done"
	child_usage = sum(e["output_tokens"] for e in _of(session.log.read_since(0), "usage", subagent="c1"))
	assert child_usage > 0
	assert summary["usage"]["output_tokens"] > child_usage


def _schema(name):
	return {
		"type": "function",
		"function": {"name": name, "description": name, "parameters": {"type": "object", "properties": {}}},
	}


GREET_EXTENSION = """
from flow_harness.tools import ToolResult, tool

@tool
async def greet(who: str = "world", *, ctx):
    return ToolResult(content=f"hi {who}")

def setup(flow):
    flow.register_tool(greet)
"""


async def test_a_named_agent_runs_with_its_own_prompt_tools_and_settings(tmp_path, monkeypatch):
	posted = []

	class RecordingClient:
		def __init__(self, *args, **kwargs):
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			return None

		async def post(self, url, *, json, headers):
			posted.append(json)

			class Response:
				def raise_for_status(self):
					pass

				def json(self):
					return {"content": "ticket 7: resolved", "is_error": False}

			return Response()

	monkeypatch.setattr("flow_harness.agent.client_tools.httpx.AsyncClient", RecordingClient)
	extension = tmp_path / "extensions" / "greet.py"
	extension.parent.mkdir()
	extension.write_text(GREET_EXTENSION)
	events: list[dict] = []
	store = SessionStore(
		str(tmp_path / "data"),
		event_sink=lambda _sid, ev: events.append(ev),
		extension_paths=[str(extension)],
	)
	lookup = SubagentConfig(
		name="Lookup",
		description="finds things",
		system_prompt="you look things up",
		tools=["read"],
		extension_tools=["greet"],
		client_tools=[_schema("find_ticket")],
		user_context={"agent": "Lookup"},
		reasoning_effort="low",
	)
	session = store.create(
		SessionConfig(
			cwd=str(tmp_path),
			tools=["read", "subagent"],
			extension_tools=[],
			client_tools=[_schema("check_mail")],
			callback_url="https://client.invalid/tools",
			user_context={"agent": "Flow"},
			reasoning_effort="high",
			subagents=[lookup],
		)
	)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "find it", agent="Lookup")]),
				AssistantMessage(content="done"),
			],
			"find it": [
				AssistantMessage(content=[ToolCall(id="c2", name="find_ticket", arguments={})]),
				AssistantMessage(content="found"),
			],
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
	assert [t["function"]["name"] for t in parent.tools] == ["read", "subagent", "check_mail"]
	assert child.system_prompt == "you look things up"
	assert [t["function"]["name"] for t in child.tools] == ["read", "greet", "find_ticket"]
	assert (parent.params["reasoning_effort"], child.params["reasoning_effort"]) == ("high", "low")
	# its client tools are called back with its own context
	assert posted[0].pop("result_token")
	assert posted == [
		{
			"callback_type": "tool",
			"session_id": session.id,
			"tool": "find_ticket",
			"args": {},
			"user_context": {"agent": "Lookup"},
			"mode": "execute",
		}
	]
	assert _of(events, "tool_result", subagent="c1")[0]["content"] == "ticket 7: resolved"
	result = _of(events, "tool_result")[0]
	assert result["content"] == "found\n\n[subagent_id: c1]" and result["details"]["agent"] == "Lookup"


def test_a_child_takes_the_run_model_and_budget_unless_its_agent_picks_its_own(tmp_path):
	budget = TokenBudget(limit=100)
	inputs = LoopInputs(
		config=SessionConfig(
			cwd=str(tmp_path),
			api_key="parent-key",
			api_base="http://parent",
			model_params={"route": "parent"},
		),
		messages=[],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
		abort=asyncio.Event(),
		model_name="mock",
		credential_id="cred",
		model=MockModel(replies=[]),
		budget=budget,
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
			child_inputs.config.model_params,
			child_inputs.reasoning_effort,
		)

	parent = (inputs.model, "mock", "cred", "parent-key", "http://parent", {"route": "parent"}, None)
	cases = [
		({}, parent),
		({"reasoning_effort": "low"}, (*parent[:-1], "low")),
		# credentials and model params travel with a model, or come on their own
		({"api_key": "child-key"}, (None, "mock", None, "child-key", None, {}, None)),
		({"model": "other"}, (None, "other", None, None, None, {}, None)),
		({"model_params": {"route": "child"}}, (None, "mock", None, None, None, {"route": "child"}, None)),
	]
	for definition, expected in cases:
		assert selection(child(**definition)) == expected, definition

	assert child().budget is budget  # the same object, so siblings share one ceiling
	# adapters report cache reads inside input_tokens, so they come back out
	child().budget.add(Usage(input_tokens=50, output_tokens=10, cache_read_tokens=20))
	assert budget.spent == 40 and not budget.exhausted
	budget.add(Usage(input_tokens=1_060, cache_read_tokens=1_000))
	assert budget.spent == 100 and budget.exhausted


def test_agent_definitions_are_checked_and_their_keys_redacted(tmp_path):
	with pytest.raises(ValidationError, match="reserved"):
		SessionConfig(subagents=[SubagentConfig(name="general")])
	with pytest.raises(ValidationError, match="unique"):
		SessionConfig(subagents=[SubagentConfig(name="a"), SubagentConfig(name="a")])
	capped = SessionStore(str(tmp_path / "capped"), tool_allowlist={"read", "subagent"})
	config = SessionConfig(cwd=str(tmp_path), subagents=[SubagentConfig(name="a", tools=["bash", "read"])])
	with pytest.raises(PolicyError, match="bash"):
		capped.create(config)

	# the API refuses inline agent credentials like the session's, and echoes them redacted
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


async def test_subagent_arguments_are_resolved_or_refused(tmp_path):
	session, events = _session(tmp_path, subagents=[SubagentConfig(name="Lookup")])
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(
					content=[
						_spawn("c1", "slow"),
						_spawn("c2", "more", subagent_id="c1"),
						_spawn("c3", "more", subagent_id="nope"),
						_spawn("c4", "more", agent="general", subagent_id="c1"),
						_spawn("c5", "x", agent="Nobody"),
						# empty arguments count as left out
						_spawn("c6", "find it", agent="Lookup", subagent_id=""),
						_spawn("c7", "ask it", agent="", subagent_id=""),
					]
				),
				AssistantMessage(content="done"),
			],
			"slow": [AssistantMessage(content="late")],
			"find it": [AssistantMessage(content="found")],
			"ask it": [AssistantMessage(content="answered")],
		}
	)
	model.gate("slow")

	handle = await session.run("go", model=model)
	await model.started["slow"].wait()
	model.gates["slow"].set()
	assert handle.task is not None
	await handle.task

	results = {r["tool_call_id"]: r for r in _of(events, "tool_result")}
	assert {cid: (r["content"], r["is_error"]) for cid, r in results.items()} == {
		"c1": ("late\n\n[subagent_id: c1]", False),
		"c2": ("[sub-agent 'c1' is still running]", True),
		"c3": ("[unknown subagent_id 'nope']", True),
		"c4": ("[pass either agent or subagent_id, not both]", True),
		"c5": ("[unknown agent 'Nobody'; available: general, Lookup]", True),
		"c6": ("found\n\n[subagent_id: c6]", False),
		"c7": ("answered\n\n[subagent_id: c7]", False),
	}
	assert (results["c6"]["details"]["agent"], results["c7"]["details"]["agent"]) == ("Lookup", "general")
	# a refused call starts no child
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1", "c6", "c7"}


async def test_nothing_inside_a_child_can_delegate(tmp_path):
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
				AssistantMessage(
					content=[_spawn("c2", "deeper"), ToolCall(id="c3", name="delegate", arguments={})]
				),
				AssistantMessage(content="gave up"),
			],
		}
	)

	await _run(session, "go", model)

	nested = {r["tool_call_id"]: r for r in _of(events, "tool_result", subagent="c1")}
	assert nested["c2"]["is_error"] and "unknown tool: subagent" in nested["c2"]["content"]
	assert nested["c3"]["content"] == "runner: absent"
	results = {r["tool_call_id"]: r for r in _of(events, "tool_result")}
	assert results["p1"]["content"] == "runner: present"
	assert "gave up" in results["c1"]["content"]
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1"}


async def test_subagents_in_one_turn_run_together_up_to_the_cap(tmp_path):
	session, events = _session(tmp_path, max_concurrent_subagents=2)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(
					content=[_spawn("c1", "left"), _spawn("c2", "right"), _spawn("c3", "third")]
				),
				AssistantMessage(content="done"),
			],
			"left": [AssistantMessage(content="L")],
			"right": [AssistantMessage(content="R")],
			"third": [AssistantMessage(content="3")],
		}
	)
	for key in ("left", "right", "third"):
		model.gate(key)

	handle = await session.run("go", model=model)
	# two children are inside their model turn at once; the third waits for a slot
	await asyncio.wait_for(asyncio.gather(model.started["left"].wait(), model.started["right"].wait()), 5)
	await asyncio.sleep(0.05)
	assert not model.started["third"].is_set()
	model.gates["left"].set()
	await asyncio.wait_for(model.started["third"].wait(), 5)
	model.gates["right"].set()
	model.gates["third"].set()
	assert handle.task is not None
	await handle.task

	assert {r["tool_call_id"]: r["content"] for r in _of(events, "tool_result")} == {
		"c1": "L\n\n[subagent_id: c1]",
		"c2": "R\n\n[subagent_id: c2]",
		"c3": "3\n\n[subagent_id: c3]",
	}
	assert {e["subagent_id"] for e in events if e.get("subagent_id")} == {"c1", "c2", "c3"}


async def test_abort_ends_every_child_running_paused_or_waiting_for_a_slot(tmp_path):
	session, events = _session(tmp_path, max_concurrent_subagents=2)
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "slow"), _spawn("c2", "risky"), _spawn("c3", "later")])
			],
			"slow": [AssistantMessage(content="1")],
			"risky": [AssistantMessage(content=[_bash("c9")])],
			"later": [AssistantMessage(content="3")],
		}
	)
	model.gate("slow")

	handle = await session.run("go", model=model)
	await model.started["slow"].wait()
	await _until(lambda: _of(events, "run_ended", subagent="c2"))  # paused for approval
	assert session.abort() is True
	assert handle.task is not None
	await handle.task

	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "aborted"
	assert [e["reason"] for e in _of(events, "run_ended", subagent="c2")] == ["paused", "aborted"]
	assert _of(events, "run_ended", subagent="c3") == []  # never started, so nothing to settle
	assert {r["tool_call_id"] for r in _of(events, "tool_result")} == {"c1", "c2", "c3"}
	assert _of(events, "run_ended")[0]["reason"] == "aborted"
	assert session.state == "idle"


async def test_a_child_that_stops_short_is_an_error_result_and_the_session_carries_on(tmp_path):
	quick = SubagentConfig(name="Quick", max_turns=1)
	session, events = _session(tmp_path, auto_approve=True, subagents=[quick])
	error = ProviderError(kind="auth", retryable=False, status_code=401, provider="mock", detail="bad key")
	model = ScriptedModel(
		{
			"go": [
				AssistantMessage(content=[_spawn("c1", "count", agent="Quick"), _spawn("c2", "boom")]),
				AssistantMessage(content="done"),
			],
			"count": [AssistantMessage(content=[_bash("c3")]), AssistantMessage(content="counted")],
		},
		errors={"boom": error},
	)

	await _run(session, "go", model)

	# one stops at its agent's own turn cap, the other on a provider error
	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "max_turns"
	assert _of(events, "run_error", subagent="c2")[0]["kind"] == "auth"
	assert _of(events, "run_ended", subagent="c2")[0]["reason"] == "error"
	results = {r["tool_call_id"]: r for r in _of(events, "tool_result")}
	assert results["c1"]["is_error"] and "[sub-agent stopped: max_turns]" in results["c1"]["content"]
	assert (
		results["c2"]["is_error"] and "[sub-agent stopped: error: ProviderError:" in results["c2"]["content"]
	)
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_a_child_approval_pauses_only_the_child_and_takes_one_answer(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [AssistantMessage(content=[_bash("c2")]), AssistantMessage(content="ran it")],
		}
	)
	gate = model.gate("risky")

	handle = await session.run("go", model=model)
	await model.started["risky"].wait()
	# nothing is answerable while no child waits
	with pytest.raises(SessionConflict):
		await session.resume({"c2": "Approve"}, approval_seq=99)
	with pytest.raises(SessionConflict):
		await session.cancel_pending()
	gate.set()
	await _until(lambda: _of(events, "run_ended", subagent="c1"))

	approval = _of(events, "approval_required", subagent="c1")[0]
	assert [call["id"] for call in approval["calls"]] == ["c2"]
	assert _of(events, "run_ended", subagent="c1")[0]["reason"] == "paused"
	assert session.state == "running" and session.transcript.pending_approval is None
	with pytest.raises(ResumeError):
		await session.resume({"c9": "Approve"}, approval_seq=approval["seq"])

	resumed = await session.resume({"c2": "Approve"}, approval_seq=approval["seq"])
	assert resumed.status == "resumed" and resumed.task is None
	with pytest.raises(SessionConflict):  # answered, but the child has not woken yet
		await session.resume({"c2": "Approve"}, approval_seq=approval["seq"])
	with pytest.raises(SessionConflict):
		await session.cancel_pending()
	assert handle.task is not None
	await handle.task

	ran = _of(events, "tool_result", subagent="c1")[0]
	assert ran["tool_call_id"] == "c2" and not ran["is_error"]
	assert [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["paused", "done"]
	assert _of(events, "tool_result")[0]["content"] == "ran it\n\n[subagent_id: c1]"
	assert _of(events, "run_ended")[-1]["reason"] == "done"


async def test_an_approval_mode_change_reaches_a_running_childs_next_gate(tmp_path):
	for initial_auto_approve in (True, False):
		cwd = tmp_path / str(initial_auto_approve)
		cwd.mkdir()
		session, events = _session(cwd, auto_approve=initial_auto_approve)
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
		assert _of(events, "tool_result")[0]["content"] == "ran it\n\n[subagent_id: c1]", initial_auto_approve


async def test_a_denied_or_cancelled_child_is_an_error_result(tmp_path):
	for how in ("deny", "cancel"):
		cwd = tmp_path / how
		cwd.mkdir()
		# a named agent's confirm list gates its own calls
		careful = SubagentConfig(name="Careful", confirm_tools=["read"])
		session, events = _session(cwd, subagents=[careful])
		model = ScriptedModel(
			{
				"go": [
					AssistantMessage(content=[_spawn("c1", "look", agent="Careful")]),
					AssistantMessage(content="done"),
				],
				"look": [
					AssistantMessage(content=[ToolCall(id="c2", name="read", arguments={"path": "x"})]),
					AssistantMessage(content="never reached"),
				],
			}
		)

		handle = await session.run("go", model=model)
		await _until(lambda: _of(events, "run_ended", subagent="c1"))
		approval = _of(events, "approval_required", subagent="c1")[0]
		assert [call["name"] for call in approval["calls"]] == ["read"], how
		assert not _of(events, "approval_required"), how  # the session's own list never named read
		if how == "deny":
			await session.resume({"c2": "Deny"}, approval_seq=approval["seq"])
		else:
			assert await session.cancel_pending() is True
		assert handle.task is not None
		await handle.task

		stopped = "denied" if how == "deny" else "cancelled"
		if how == "deny":
			assert _of(events, "run_ended", subagent="c1")[-1]["reason"] == "denied"
		child = _of(events, "tool_result", subagent="c1")[0]
		assert child["tool_call_id"] == "c2" and child["is_error"] and stopped in child["content"], how
		result = _of(events, "tool_result")[0]
		assert result["is_error"] and f"[sub-agent stopped: {stopped}]" in result["content"], how
		assert session.state == "idle" and _of(events, "run_ended")[-1]["reason"] == "done", how


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


async def test_a_continued_child_has_what_an_abort_or_a_crash_left_open_closed_first(tmp_path):
	for how in ("abort", "restart"):
		base = tmp_path / how
		base.mkdir()
		session, events = _session(base)
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
		await _until(
			lambda: [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["done", "paused"]
		)
		assert handle.task is not None
		if how == "abort":
			assert session.abort() is True
			await handle.task
			continued = session
		else:  # the log as a crash leaves it, opened by a fresh process
			shutil.copytree(base / "data", base / "restarted")
			continued = SessionStore(
				str(base / "restarted"), event_sink=lambda _sid, ev: events.append(ev)
			).get(session.id)
		await _run(continued, "again", model)

		third = next(r for r in model.requests if _last_user(r.messages) == "third")
		assert [m.type for m in third.messages] == ["user_message", "assistant_message"] * 2 + [
			"tool_result",
			"user_message",
		], how
		closed = third.messages[4]
		assert closed.tool_call_id == "c9" and (
			("interrupted" if how == "abort" else "cancelled") in closed.content
		), how
		assert _of(events, "tool_result")[-1]["content"] == "three\n\n[subagent_id: c1]", how
		if how == "restart":  # the paused session's own run is still parked in this process
			session.abort()
			await handle.task
