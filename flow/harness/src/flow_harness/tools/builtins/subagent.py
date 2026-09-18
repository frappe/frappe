"""The subagent builtin: hands a task to a child agent that the session runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, replace
from typing import Annotated

from flow_harness.session.config import GENERAL_AGENT, SubagentConfig
from flow_harness.tools.builtins.common import truncate
from flow_harness.tools.tool import Tool, ToolContext, ToolResult, tool

_FAILED = frozenset({"error", "aborted", "max_turns", "budget", "cancelled"})
_GENERAL = SubagentConfig(name=GENERAL_AGENT, description="a copy of you with a fresh context")


@dataclass
class SubagentOutcome:
	"""How a sub-agent run ended, for the tool to report."""

	end_reason: str
	text: str
	error: str | None = None


@tool(
	concurrent=True,
	prompt_snippet="Hand a self-contained task to a sub-agent with a fresh context",
	display_template="Sub-agent: {{ description }}",
)
async def subagent(
	task: Annotated[str, "The complete brief: the goal, what you already know, and exactly what to return"],
	description: Annotated[str, "A three to five word label for the task, shown to the user"],
	agent: Annotated[str | None, "The agent to run, from the list below; omitted means general"] = None,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Hand a self-contained task to a sub-agent and get back only its final answer.

	The sub-agent works in a fresh context: it sees nothing of this conversation, so
	`task` must carry everything it needs: the goal, what you already know, and exactly
	what to return. Use it for a bounded task whose intermediate output would clutter
	your context, or when a listed agent is built for the job. Do a quick lookup or a
	handful of tool calls yourself. Calls made in the same reply run at the same time.
	Sub-agents cannot delegate further.
	"""
	# the session binds its runner with `bind_subagent`; unbound, the tool cannot run
	return ToolResult(content="[sub-agents are not available here]", is_error=True)


def bind_subagent(
	run: Callable[[str, str, SubagentConfig], Awaitable[SubagentOutcome]], subagents: Iterable[SubagentConfig]
) -> Tool:
	"""The tool wired to a session's runner, with the session's agents listed in its description."""
	known = {item.name: item for item in (_GENERAL, *subagents)}
	lines = [
		f"- {item.name}: {item.description}" if item.description else f"- {item.name}"
		for item in known.values()
	]

	async def bound(task: str, description: str, agent: str | None = None, *, ctx: ToolContext) -> ToolResult:
		subagent_config = known.get(agent or GENERAL_AGENT)
		if subagent_config is None:
			return ToolResult(
				content=f"[unknown agent {agent!r}; available: {', '.join(known)}]", is_error=True
			)
		return _report(await run(ctx.tool_call_id, task, subagent_config), subagent_config.name)

	description = subagent.description + "\n\nAvailable agents:\n" + "\n".join(lines)
	return replace(subagent, func=bound, description=description)


def _report(outcome: SubagentOutcome, agent: str) -> ToolResult:
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
	return ToolResult(
		content="\n\n".join(parts),
		is_error=failed,
		details={"agent": agent, "end_reason": outcome.end_reason, "truncation": trunc},
	)
