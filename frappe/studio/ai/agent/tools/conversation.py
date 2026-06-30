"""Conversation tools — the agent's way of pausing the loop to talk to the user.

Both are *terminal*: calling one ends the turn and hands control back to the user.
Approval of a proposed plan is just the user's next ordinary message.
"""

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.session import AISession


def _ask_clarification(ctx, args: dict) -> None:
	question = (args.get("question") or "Could you clarify?").strip()
	options = [str(o).strip() for o in (args.get("options") or []) if str(o).strip()]
	# Persist + commit BEFORE emitting: the realtime event triggers a session reload on
	# the client, which must see this message already in the DB.
	AISession.try_append_message(
		ctx.session_id,
		"assistant",
		question,
		message_type="clarification",
		task_type="agent",
		metadata={"status": "clarification", "options": options},
	)
	frappe.db.commit()
	ctx.emit("clarify", question=question, options=options)


def normalize_sections(raw) -> list[str]:
	"""Accept sections as a newline-delimited string (the robust contract for weaker
	models) OR a list. Strip bullets/leading dashes and stray quotes."""
	if isinstance(raw, str):
		items = raw.splitlines()
	elif isinstance(raw, list):
		items = [str(s) for s in raw]
	else:
		items = []
	out = []
	for item in items:
		s = item.strip().lstrip("-•*").strip().strip("'\"").strip()
		if s:
			out.append(s)
	return out


def _propose_plan(ctx, args: dict) -> None:
	headline = (args.get("headline") or "Here's my plan").strip()
	sections = normalize_sections(args.get("sections"))
	palette = (args.get("palette") or "").strip()
	AISession.try_append_message(
		ctx.session_id,
		"assistant",
		headline,
		message_type="clarification",
		task_type="agent",
		metadata={"status": "plan_summary", "headline": headline, "sections": sections, "palette": palette},
	)
	frappe.db.commit()
	ctx.emit(
		"clarify",
		question=headline,
		options=[],
		plan_summary=True,
		headline=headline,
		sections=sections,
		palette=palette,
	)


ask_clarification = Tool(
	name="ask_clarification",
	side="terminal",
	description=(
		"Ask the user ONE focused question to gather information you need (e.g. brand name, "
		"positioning, audience, visual style). Ends your turn and waits for their reply. Provide "
		"2–5 short options when there are sensible choices; omit options for open-ended answers "
		"like a name (the user can type their reply)."
	),
	parameters={
		"type": "object",
		"properties": {
			"question": {"type": "string", "description": "A single, focused question."},
			"options": {
				"type": "array",
				"items": {"type": "string"},
				"description": "Optional: 2–5 short plain-text answer choices. Omit for open-ended questions.",
			},
		},
		"required": ["question"],
	},
	handler=_ask_clarification,
)

propose_plan = Tool(
	name="propose_plan",
	side="terminal",
	description=(
		"Before building a NEW page or doing a major redesign, present a short plan and wait for "
		"the user to approve or refine it. Ends your turn. Never call this twice in a row: if a "
		"plan is already pending and the user approved it, call generate_page instead. Only "
		"re-propose when the user asked for changes."
	),
	parameters={
		"type": "object",
		"properties": {
			"headline": {
				"type": "string",
				"description": "One concrete line stating what the page is and who it's for — not a slogan.",
			},
			"sections": {
				"type": "string",
				"description": (
					"3–5 sections as ONE string, each section on its OWN LINE (separate with a newline). "
					"Do NOT send a JSON array. Make each line decision-useful: the real headline/key copy "
					"it will use (in 'single quotes'), what's concretely in it, and the layout."
				),
			},
			"palette": {"type": "string", "description": "Palette description with hex codes."},
		},
		"required": ["headline", "sections"],
	},
	handler=_propose_plan,
)

TOOLS = [ask_clarification, propose_plan]
