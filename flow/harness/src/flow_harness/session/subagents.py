"""Sub-agents: the children the `subagent` tool starts inside a session's run."""

from __future__ import annotations

import asyncio
import json
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
from flow_harness.session.prompt import strip_tool_from_prompt
from flow_harness.session.transcript import PendingApproval, Transcript
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
		max_concurrent: int,
	):
		self._commit = commit
		self._run_error = run_error
		self._compose_tools = compose_tools
		self._slots = asyncio.Semaphore(max_concurrent)
		self._pauses: dict[int | None, _Pause] = {}  # by approval seq, while a child waits on it

	async def run(
		self, inputs: loop.LoopInputs, call_id: str, task: str, agent: str | None
	) -> SubagentOutcome:
		"""Run `agent` through `task` as the sub-agent named by its call, in the run of `inputs`."""
		config = _agent(inputs.config, agent)
		child = Transcript(call_id)
		async with self._slots:
			return await self._drive(
				_child_inputs(inputs, child, config, self._compose_tools), child, task, config.name
			)

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
				inputs, context_tokens=child.context_tokens, context_message_count=child.context_message_count
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
		self, child: Transcript, *, reason: Literal["aborted", "error"], error: Exception | None = None
	) -> None:
		for repair in child.missing_results():
			self._record(child, repair)
		if error is not None:
			self._record(child, self._run_error(error))
		self._record(child, RunEnded(reason=reason))

	def _record(self, child: Transcript, event: AnyEvent) -> None:
		event.subagent_id = child.subagent_id
		self._commit(event)
		if event.durable:
			child.record(event)


def _child_inputs(
	inputs: loop.LoopInputs,
	child: Transcript,
	agent: SubagentConfig,
	compose_tools: Callable[[SessionConfig], dict[str, Tool]],
) -> loop.LoopInputs:
	"""The run's inputs with the child's transcript, and the agent's prompt, tools and model where set."""
	config = inputs.config
	prompt = agent.system_prompt
	if prompt is None and config.system_prompt is not None:
		prompt = strip_tool_from_prompt(config.system_prompt, subagent.name)
	own_model = (agent.model, agent.api_key, agent.api_base) != (None, None, None)
	if own_model:
		config = config.model_copy(update={"api_key": agent.api_key, "api_base": agent.api_base})
	tools = inputs.server_tools or {}
	if agent.tools is not None:
		tools = compose_tools(config.model_copy(update={"tools": agent.tools}))
	return replace(
		inputs,
		config=config.model_copy(update={"system_prompt": prompt}),
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
