"""Sub-agents: the children the `subagent` tool starts inside a session's run."""

from __future__ import annotations

import asyncio
import json
import weakref
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, replace
from typing import Literal

from flow_harness.agent import loop
from flow_harness.events import (
	AnyEvent,
	AssistantMessage,
	RunEnded,
	RunError,
	ToolResult,
	UserMessage,
)
from flow_harness.model.cancellation import ModelCancelled, await_with_cancellation
from flow_harness.session.config import GENERAL_AGENT, SessionConfig, SubagentConfig, known_agents
from flow_harness.session.log import SessionLog
from flow_harness.session.prompt import strip_tool_from_prompt
from flow_harness.session.transcript import PendingApproval, Transcript, active_path
from flow_harness.tools import SubagentOutcome, Tool
from flow_harness.tools.builtins.subagent import subagent

CANCELLED = json.dumps({"status": "cancelled", "message": "User cancelled this pending tool call."})


@dataclass
class _Pause:
	"""A batch a child waits on, and where its answers go; None closes it as cancelled."""

	approval: PendingApproval
	answers: asyncio.Future[dict[str, str] | None]


class SubagentRunner:
	"""Runs a session's sub-agents: each child is a transcript driven through the loop with
	the run's inputs, its events committed to the session's log under the child's id."""

	def __init__(
		self,
		commit: Callable[[AnyEvent], None],
		run_error: Callable[[Exception], RunError],
		compose_tools: Callable[[SessionConfig], dict[str, Tool]],
		log: SessionLog,
		max_concurrent: int,
	):
		# a strong ref would loop back to the session, so an evicted one would not free at once
		self._commit_ref = weakref.WeakMethod(commit)
		self._run_error = run_error
		self._compose_tools = compose_tools
		self._log = log  # a continued child is rebuilt from it
		self._slots = asyncio.Semaphore(max_concurrent)
		self._running: set[str] = set()  # children in flight, by id
		self._pauses: dict[int | None, _Pause] = {}  # by approval seq, while a child waits on it

	async def run(
		self, inputs: loop.LoopInputs, call_id: str, task: str, agent: str | None, subagent_id: str | None
	) -> SubagentOutcome:
		"""Run `agent` through `task` as a new child named by its call, or continue child `subagent_id`."""
		child_id = subagent_id or call_id
		if subagent_id is None:
			child, config = Transcript(child_id), _agent(inputs.config, agent)
		elif agent is not None:
			raise ValueError("pass either agent or subagent_id, not both")
		else:
			child, config = self._continued(inputs.config, child_id)
		self._running.add(child_id)
		try:
			async with self._slots:
				return await self._drive(
					_child_inputs(inputs, child, config, self._compose_tools),
					child,
					task,
					config.name,
				)
		finally:
			self._running.discard(child_id)

	def pending(self, approval_seq: int | None) -> PendingApproval | None:
		"""The batch a child waits on under `approval_seq`, if any."""
		pause = self._pauses.get(approval_seq)
		return pause.approval if pause is not None else None

	def answer(self, approval_seq: int | None, answers: dict[str, str]) -> None:
		"""Wake the child waiting on `approval_seq` with its answers."""
		self._pauses.pop(approval_seq).answers.set_result(dict(answers))

	def cancel_pending(self) -> bool:
		"""Close every batch a child waits on; False when there is none."""
		pauses = list(self._pauses.values())
		self._pauses.clear()
		for pause in pauses:
			pause.answers.set_result(None)
		return bool(pauses)

	def _continued(self, config: SessionConfig, subagent_id: str) -> tuple[Transcript, SubagentConfig]:
		"""The child `subagent_id` rebuilt from the log for one more task, with the agent it ran as."""
		if subagent_id in self._running:
			raise ValueError(f"sub-agent {subagent_id!r} is still running")
		name = _recorded_agent(self._log, subagent_id)
		if name is None:
			raise ValueError(f"unknown subagent_id {subagent_id!r}")
		child = Transcript.replay(self._log, subagent_id=subagent_id)
		self._close_open_calls(child)
		return child, _agent(config, name)

	def _close_open_calls(self, child: Transcript) -> None:
		"""Close what an abort or a crash left open in the child: its pause, then any call nothing will answer."""
		approval = child.pending_approval
		if approval is not None:
			for call in approval.calls:
				self._record(
					child,
					ToolResult(tool_call_id=call.id, name=call.name, content=CANCELLED, is_error=True),
				)
		for repair in child.missing_results():
			self._record(child, repair)

	async def _drive(
		self, inputs: loop.LoopInputs, child: Transcript, task: str, agent: str
	) -> SubagentOutcome:
		"""Commit the child's events and report how it went; when its loop raises instead, settle it here."""
		text = ""
		end_reason: str = "done"
		error: str | None = None
		try:
			async for event in self._turns(inputs, child, task):
				self._record(child, event)
				if isinstance(event, AssistantMessage) and event.text:
					text = event.text
				elif isinstance(event, RunError):
					error = event.message
				elif isinstance(event, RunEnded):
					end_reason = event.reason
			if end_reason == "paused":  # only a cancelled batch leaves the pause behind
				end_reason = "cancelled"
		except (ModelCancelled, asyncio.CancelledError) as cancelled:
			self._settle(child, reason="aborted")
			end_reason = "aborted"
			if isinstance(cancelled, asyncio.CancelledError):
				raise
		except Exception as failure:
			self._settle(child, reason="error", error=failure)
			end_reason, error = "error", f"{type(failure).__name__}: {failure}"
		return SubagentOutcome(agent=agent, end_reason=end_reason, text=text, error=error)

	async def _turns(self, inputs: loop.LoopInputs, child: Transcript, task: str) -> AsyncIterator[AnyEvent]:
		"""The child's run, continued past each approval pause a human answers."""
		async for event in loop.run(UserMessage(content=task), inputs):
			yield event
		while (pending_approval := child.pending_approval) is not None:
			answers = await self._wait_for_answers(pending_approval, inputs.abort)
			if answers is None:  # cancel_pending closed the batch
				for call in pending_approval.calls:
					yield ToolResult(tool_call_id=call.id, name=call.name, content=CANCELLED, is_error=True)
				return
			continued = replace(
				inputs,
				context_tokens=child.context_tokens,
				context_message_count=child.context_message_count,
			)
			async for event in loop.resume(pending_approval, answers, continued):
				yield event

	async def _wait_for_answers(
		self, pending_approval: PendingApproval, abort: asyncio.Event
	) -> dict[str, str] | None:
		"""Park the child until `answer` or `cancel_pending` settles its batch; abort raises."""
		pause = self._pauses[pending_approval.seq] = _Pause(
			pending_approval, asyncio.get_running_loop().create_future()
		)
		try:
			return await await_with_cancellation(pause.answers, abort)
		finally:
			self._pauses.pop(pending_approval.seq, None)  # already gone unless the run aborted

	def _settle(
		self,
		child: Transcript,
		*,
		reason: Literal["aborted", "error"],
		error: Exception | None = None,
	) -> None:
		for repair in child.missing_results():
			self._record(child, repair)
		if error is not None:
			self._record(child, self._run_error(error))
		self._record(child, RunEnded(reason=reason))

	def _record(self, child: Transcript, event: AnyEvent) -> None:
		event.subagent_id = child.subagent_id
		commit = self._commit_ref()
		assert commit is not None  # a child only runs inside its session's run
		commit(event)
		if event.durable:
			child.record(event)


def _child_inputs(
	inputs: loop.LoopInputs,
	child: Transcript,
	agent: SubagentConfig,
	compose_tools: Callable[[SessionConfig], dict[str, Tool]],
) -> loop.LoopInputs:
	"""The run's inputs with the child's transcript, and what the agent sets of its own: prompt,
	tools, model, client tools, confirm list, turn cap and callback context."""
	config = inputs.config
	overrides = {  # the session's values the agent replaces with its own
		name: value
		for name in ("client_tools", "confirm_tools", "max_turns", "user_context")
		if (value := getattr(agent, name)) is not None
	}
	prompt = agent.system_prompt
	if prompt is None and config.system_prompt is not None:
		prompt = strip_tool_from_prompt(config.system_prompt, subagent.name)
	own_model = (agent.model, agent.api_key, agent.api_base, agent.model_params) != (None,) * 4
	if own_model:
		config = config.model_copy(
			update={
				"api_key": agent.api_key,
				"api_base": agent.api_base,
				"model_params": agent.model_params or {},
			}
		)
	tools = inputs.server_tools or {}
	own_tools = {  # composed afresh when the agent picks its own builtin or extension tools
		name: value for name in ("tools", "extension_tools") if (value := getattr(agent, name)) is not None
	}
	if own_tools:
		tools = compose_tools(config.model_copy(update=own_tools))
	return replace(
		inputs,
		config=config.model_copy(update={"system_prompt": prompt, **overrides}),
		approval_config=inputs.approval_config or inputs.config,
		messages=child.messages,
		context_tokens=child.context_tokens,
		context_message_count=child.context_message_count,
		next_steering=None,
		server_tools={name: tool for name, tool in tools.items() if name != subagent.name},
		run_subagent=None,  # nothing inside a child can delegate
		model=None if own_model else inputs.model,
		model_name=agent.model or inputs.model_name,
		credential_id=None if own_model else inputs.credential_id,
		reasoning_effort=agent.reasoning_effort or inputs.reasoning_effort,
	)


def _agent(config: SessionConfig, name: str | None) -> SubagentConfig:
	"""The agent to run as: `name` from the session's list, or general when unnamed."""
	known = known_agents(config.subagents)
	agent = known.get(name or GENERAL_AGENT)
	if agent is None:
		raise ValueError(f"unknown agent {name!r}; available: {', '.join(known)}")
	return agent


def _recorded_agent(log: SessionLog, subagent_id: str) -> str | None:
	"""The agent a child ran as, from the result of its first run; None when no such child ran."""
	for row in active_path(log.read_since(0)):
		if row.get("type") == "tool_result" and row.get("details", {}).get("subagent_id") == subagent_id:
			return row["details"]["agent"]
	return None
