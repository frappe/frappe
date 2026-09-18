"""The subagent builtin end to end: a child run inside the session, its rows tagged in
the session's log, parallel children under the cap, and how a child's end reaches the
model."""

import asyncio
from dataclasses import replace

from flow_harness.agent.loop import HookDecision
from flow_harness.events import AssistantMessage, ToolCall
from flow_harness.model import ProviderError
from flow_harness.model.mock import MockModel, _last_user
from flow_harness.server.routes.sessions import _summary
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
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


def _spawn(cid, task):
	return ToolCall(id=cid, name="subagent", arguments={"task": task, "description": "a task"})


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


async def test_a_gated_tool_inside_a_child_cancels_its_batch(tmp_path):
	session, events = _session(tmp_path)
	model = ScriptedModel(
		{
			"go": [AssistantMessage(content=[_spawn("c1", "risky")]), AssistantMessage(content="done")],
			"risky": [
				AssistantMessage(content=[ToolCall(id="c2", name="bash", arguments={"command": "true"})]),
				AssistantMessage(content="never reached"),
			],
		}
	)

	await _run(session, "go", model)

	assert [e["reason"] for e in _of(events, "run_ended", subagent="c1")] == ["paused"]
	cancelled = _of(events, "tool_result", subagent="c1")[0]
	assert cancelled["tool_call_id"] == "c2" and cancelled["is_error"] and "cancelled" in cancelled["content"]
	result = _of(events, "tool_result")[0]
	assert result["is_error"] and "[sub-agent stopped: cancelled]" in result["content"]
	assert session.state == "idle" and _of(events, "run_ended")[-1]["reason"] == "done"


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
