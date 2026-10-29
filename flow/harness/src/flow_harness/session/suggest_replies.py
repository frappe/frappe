"""Suggested replies: one call after a run that reuses the chat's prompt cache."""

from __future__ import annotations

import json
import re

from flow_harness.events import AssistantMessage, RepliesSuggested, Usage
from flow_harness.model.base import Model, ModelRequest

MIN_REPLIES, MAX_REPLIES = 2, 4
MAX_REPLY_CHARS = 200

REPLIES_PROMPT = (
	"What might I, the user, ask you next? Reply with only a JSON object and call no tools: "
	'{"replies": [two to four short follow-ups I would send you in this chat], "multi_select": false}. '
	"Each is the next step I'd likely want or, when your last reply asked me something, its "
	"likely answers. Set multi_select to true when I may pick several together. "
	'Reply {"replies": []} when no next step is clear.'
)

_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


async def suggest_replies(
	model: Model, request: ModelRequest
) -> tuple[RepliesSuggested | None, Usage | None]:
	"""The user's likely next messages, or None. `request` ends with `REPLIES_PROMPT`."""
	response: AssistantMessage | None = None
	usage: Usage | None = None
	async for event in model.run(request):
		if isinstance(event, AssistantMessage):
			response = event
		elif isinstance(event, Usage):
			usage = event.model_copy(update={"standalone": True, "purpose": "replies"})
	if response is None or response.stop_reason != "stop":
		return None, usage
	return parse_replies(response.text), usage


def parse_replies(text: str) -> RepliesSuggested | None:
	match = _OBJECT_RE.search(text)
	try:
		data = json.loads(match.group()) if match else None
	except ValueError:
		return None
	if not isinstance(data, dict) or not isinstance(data.get("replies"), list):
		return None
	replies = [reply.strip() for reply in data["replies"] if isinstance(reply, str)]
	if (
		not MIN_REPLIES <= len(replies) <= MAX_REPLIES
		or "" in replies
		or len(set(replies)) < len(replies)
		or any(len(reply) > MAX_REPLY_CHARS for reply in replies)
	):
		return None
	return RepliesSuggested(replies=replies, multi_select=data.get("multi_select") is True)
