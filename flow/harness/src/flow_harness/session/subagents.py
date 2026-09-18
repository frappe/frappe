"""Sub-agents: the children the `subagent` tool starts inside a session's run."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
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
from flow_harness.model.cancellation import ModelCancelled
from flow_harness.session.config import SessionConfig, SubagentConfig
from flow_harness.session.prompt import strip_tool_from_prompt
from flow_harness.session.transcript import Transcript
from flow_harness.tools import Tool
from flow_harness.tools.builtins.subagent import SubagentOutcome, subagent

CANCELLED = json.dumps({"status": "cancelled", "message": "User cancelled this pending tool call."})


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

	async def run(
		self, inputs: loop.LoopInputs, call_id: str, task: str, agent: SubagentConfig
	) -> SubagentOutcome:
		"""Run `agent` through `task` as the sub-agent named by its call, in the run of `inputs`."""
		child = Transcript(call_id)
		async with self._slots:
			return await self._drive(_child_inputs(inputs, child, agent, self._compose_tools), child, task)

	async def _drive(self, inputs: loop.LoopInputs, child: Transcript, task: str) -> SubagentOutcome:
		"""Run the child's turn to its end and report how it went."""
		text = ""
		end_reason: str = "done"
		error: str | None = None
		try:
			async for event in loop.run(UserMessage(content=task), inputs):
				self._record(child, event)
				if isinstance(event, AssistantMessage) and event.text:
					text = event.text
				elif isinstance(event, RunError):
					error = event.message
				elif isinstance(event, RunEnded):
					end_reason = event.reason
			if end_reason == "paused":  # nothing answers a child's approval yet: close its batch
				approval = child.pending_approval
				assert approval is not None  # the pause put it there
				for call in approval.calls:
					self._record(
						child,
						ToolResult(tool_call_id=call.id, name=call.name, content=CANCELLED, is_error=True),
					)
				end_reason = "cancelled"
		except (ModelCancelled, asyncio.CancelledError) as cancelled:
			self._settle(child, reason="aborted")
			end_reason = "aborted"
			if isinstance(cancelled, asyncio.CancelledError):
				raise
		except Exception as failure:
			self._settle(child, reason="error", error=failure)
			end_reason, error = "error", f"{type(failure).__name__}: {failure}"
		return SubagentOutcome(end_reason=end_reason, text=text, error=error)

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
		model=None if own_model else inputs.model,
		model_name=agent.model or inputs.model_name,
		credential_id=None if own_model else inputs.credential_id,
		reasoning_effort=agent.reasoning_effort or inputs.reasoning_effort,
	)
