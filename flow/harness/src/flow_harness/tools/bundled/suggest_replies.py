"""suggest_replies: offers the user a few next messages, sent with a tap."""

from __future__ import annotations

from typing import Annotated

from flow_harness.tools.tool import ToolContext, ToolResult, tool

MIN_REPLIES, MAX_REPLIES = 2, 4


@tool(prompt_snippet="Offer the user a few short next messages, sent with a tap", ends_run=True)
async def suggest_replies(
	replies: Annotated[list[str], "two to four short messages, in the user's voice"],
	multi_select: Annotated[bool, "let the user pick several and send them together"] = False,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Offer the user two to four next messages, shown as buttons under your reply.

	Call it last, once your reply is written: it ends your turn. Each is a message the user
	would send, in their words and only a few of them: the next steps they are likely to want
	or, when your reply asks a question, its likely answers. Set multi_select when they may pick
	several. They can always type something else. Skip it when no next step is clear.
	"""
	replies = [reply.strip() for reply in replies]
	if not MIN_REPLIES <= len(replies) <= MAX_REPLIES or "" in replies or len(set(replies)) < len(replies):
		return ToolResult(
			content=f"[give {MIN_REPLIES} to {MAX_REPLIES} short, distinct replies]", is_error=True
		)
	return ToolResult(
		content="[shown to the user]", details={"replies": replies, "multi_select": multi_select}
	)
