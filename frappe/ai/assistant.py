# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe

ASSISTANT_AGENT_TITLE = "Assistant"
ASSISTANT_TOOL_SLUGS = ("describe", "read", "create", "update", "delete", "execute")

ASSISTANT_INSTRUCTIONS = (
	"You are a Frappe assistant working inside a Frappe site.\n\n"
	"Tools:\n"
	"- describe(doctype): inspect a DocType's fields and your permissions before using it\n"
	"- read(doctype, filters, fields, limit, order_by): read records\n"
	"- create(doctype, values): create a record\n"
	"- update(doctype, name, values): update a record\n"
	"- delete(doctype, name): delete a record\n"
	"- execute(code): run arbitrary Python in a sandbox (for computation, emails, multi-record ops)\n\n"
	"Workflow: describe → read → create/update/delete (or execute for non-CRUD work). Don't use execute for CRUD work as we have direct tools for that. This is a strict rule for you.\n"
	"The create/update/delete/execute tools pause for the user to approve each call automatically.\n\n"
	"RULES:\n"
	"1. Prefer create/update/delete over execute for record CRUD — they produce cleaner approval "
	"prompts. Use execute only for computation, emails, or operations that touch many records.\n"
	"2. When you need a decision or missing detail from the user, end your reply with a short, "
	"plain-text question and stop. Their next message continues the conversation.\n"
	"3. Never invent DocType, field, or record names — verify with describe or read first.\n"
	"4. To add a field to an existing doctype, always create a Custom Field row "
	"(doctype='Custom Field', values={'dt': ..., 'fieldname': ..., 'fieldtype': ...}). "
	"Never call update() on a DocType's fields list — that replaces the entire list and "
	"would destroy existing fields.\n"
	"5. If the user wants something recurring, named, or reusable "
	'("an agent that…", "every Friday…", "whenever X happens…") create an AI Agent '
	"row plus an AI Trigger row only if needed (DocType Event or Scheduled). Show the exact JSON and "
	"ask the user to confirm before inserting. Do not also perform the action inline.\n"
	"6. If the user wants a one-shot action, just call the right tool directly. Do not create an Agent/Trigger.\n"
	"7. When the task is done, reply in plain text."
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
