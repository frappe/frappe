# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe

ASSISTANT_AGENT_TITLE = "Assistant"
ASSISTANT_TOOL_SLUGS = ("introspect", "query", "execute", "ask_user")

ASSISTANT_INSTRUCTIONS = (
	"You are a Frappe assistant working inside a Frappe site. The user asks you to "
	"read or change data within it.\n\n"
	"Tools:\n"
	"- introspect(doctype): inspect a DocType's fields and your permissions before using it\n"
	"- query(doctype, filters, fields, limit, order_by): read records\n"
	"- execute(code): run Python in a sandbox; use it for writes, emails, and computation\n"
	"- ask_user(prompt, options, multi_select): pause and ask the user a question\n\n"
	"Workflow: introspect → query → ask_user to confirm → execute.\n\n"
	"RULES:\n"
	"1. Before any write, delete, or email you MUST call ask_user() to confirm — "
	"never ask in plain text and never act without confirmation.\n"
	"2. Never end a reply with a question — use ask_user() instead.\n"
	"3. Never invent DocType, field, or record names — verify with introspect or query first.\n"
	"4. If the user wants something recurring, named, or reusable "
	'("an agent that…", "every Friday…", "whenever X happens…") create an AI Agent '
	"row plus an AI Trigger row (DocType Event or Scheduled). Show the exact JSON via "
	"ask_user() before inserting. Do not also perform the action inline.\n"
	"5. If the user wants a one-shot action, confirm via ask_user() and execute() it "
	"directly. Do not create an Agent/Trigger.\n"
	"6. When the task is done, reply in plain text."
)


def sync_builtin_assistant(model: str | None = None) -> None:
	"""Create the system Assistant agent if missing. `model` defaults to the first enabled AI Model."""
	from frappe.ai.tools.builtins import sync_builtin_tools

	if frappe.db.exists("AI Agent", ASSISTANT_AGENT_TITLE):
		return

	model_name = model or frappe.db.get_value("AI Model", {"enabled": 1}, "name")
	if not model_name:
		return

	sync_builtin_tools()
	frappe.get_doc(
		{
			"doctype": "AI Agent",
			"title": ASSISTANT_AGENT_TITLE,
			"model": model_name,
			"instructions": ASSISTANT_INSTRUCTIONS,
			"tools": [{"tool": slug} for slug in ASSISTANT_TOOL_SLUGS],
			"enabled": 1,
			"is_system_generated": 1,
		}
	).insert(ignore_permissions=True)
