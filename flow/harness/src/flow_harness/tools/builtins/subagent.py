"""The subagent builtin: hands a task to a child agent that the session runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Annotated

from flow_harness.tools.builtins.common import truncate
from flow_harness.tools.tool import Tool, ToolContext, ToolResult, tool

_FAILED = frozenset({"error", "aborted", "max_turns", "budget", "cancelled"})


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
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Hand a self-contained task to a sub-agent and get back only its final answer.

	The sub-agent is a copy of you with a fresh context: it sees nothing of this
	conversation, so `task` must carry everything it needs: the goal, what you already
	know, and exactly what to return. Use it for a bounded task whose intermediate
	output would clutter your context. Do a quick lookup or a handful of tool calls
	yourself. Calls made in the same reply run at the same time. Sub-agents cannot
	delegate further.
	"""
	# the session binds its runner with `bind_subagent`; unbound, the tool cannot run
	return ToolResult(content="[sub-agents are not available here]", is_error=True)


def bind_subagent(run: Callable[[str, str], Awaitable[SubagentOutcome]]) -> Tool:
	"""The tool wired to a session's runner, which takes the call id and the task."""

	async def bound(task: str, description: str, *, ctx: ToolContext) -> ToolResult:
		return _report(await run(ctx.tool_call_id, task))

	return replace(subagent, func=bound)


def _report(outcome: SubagentOutcome) -> ToolResult:
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
		details={"end_reason": outcome.end_reason, "truncation": trunc},
	)
