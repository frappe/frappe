"""The subagent builtin: hands a task to a child agent that the session runs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from flow_harness.session.config import SubagentConfig, known_agents
from flow_harness.tools.builtins.common import truncate
from flow_harness.tools.tool import SubagentOutcome, ToolContext, ToolResult, tool

_FAILED = frozenset({"error", "aborted", "max_turns", "budget", "cancelled", "denied"})


@tool(
	concurrent=True,
	prompt_snippet="Hand a self-contained task to a sub-agent with a fresh context",
	display_template="Sub-agent: {{ description }}",
)
async def subagent(
	description: Annotated[str, "A three to five word label for the task, shown to the user"],
	task: Annotated[str, "The complete brief: the goal, what you already know, and exactly what to return"],
	agent: Annotated[str | None, "The agent to run, from the list below; omitted means general"] = None,
	subagent_id: Annotated[
		str | None, "Continue an earlier sub-agent, keeping its context, by the id from its result"
	] = None,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Hand a self-contained task to a sub-agent and get back only its final answer.

	The sub-agent works in a fresh context: it sees nothing of this conversation, so
	`task` must carry everything it needs: the goal, what you already know, and exactly
	what to return. Use it for a bounded task whose intermediate output would clutter
	your context, or when a listed agent is built for the job. Do a quick lookup or a
	handful of tool calls yourself. Calls made in the same reply run at the same time.
	Sub-agents cannot delegate further. To continue a sub-agent with its context intact,
	pass the `subagent_id` from its earlier result.
	"""
	if ctx.run_subagent is None:
		return ToolResult(content="[sub-agents are not available here]", is_error=True)
	agent, subagent_id = agent or None, subagent_id or None  # models send "" for skipped options
	try:
		outcome = await ctx.run_subagent(ctx.tool_call_id, task, agent, subagent_id)
	except ValueError as error:  # refused before anything ran
		return ToolResult(content=f"[{error}]", is_error=True)
	return _report(outcome, subagent_id or ctx.tool_call_id)


def describe_agents(subagents: Iterable[SubagentConfig]) -> str:
	"""The tool's description with the session's agents listed, for the model to pick from."""
	lines = [
		f"- {item.name}: {item.description}" if item.description else f"- {item.name}"
		for item in known_agents(subagents).values()
	]
	return subagent.description + "\n\nAvailable agents:\n" + "\n".join(lines)


def _report(outcome: SubagentOutcome, subagent_id: str) -> ToolResult:
	body, trunc = truncate(outcome.text, keep="head")
	parts = [body or "[the sub-agent gave no answer]"]
	failed = outcome.end_reason in _FAILED
	if failed:
		detail = f": {outcome.error}" if outcome.error else ""
		parts.append(f"[sub-agent stopped: {outcome.end_reason}{detail}]")
	if trunc["truncated"]:
		parts.append(
			f"[answer truncated to the first {trunc['output_lines']} of {trunc['total_lines']} lines]"
		)
	parts.append(f"[subagent_id: {subagent_id}]")
	return ToolResult(
		content="\n\n".join(parts),
		is_error=failed,
		details={
			"subagent_id": subagent_id,
			"agent": outcome.agent,
			"end_reason": outcome.end_reason,
			"truncation": trunc,
		},
	)
