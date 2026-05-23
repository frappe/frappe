# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.ai.agent import Question
from frappe.ai.tool import Tool, tool
from frappe.utils.safe_exec import safe_exec

MAX_QUERY_LIMIT = 200
LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading"})


@tool
def introspect(doctype: str) -> dict[str, Any]:
	"""Inspect a DocType's schema before reading or acting on it.

	Returns its fields (fieldname, label, type, options for Link/Select/Table, required)
	and the current user's permissions on it. Use this to learn what data exists and
	what you are allowed to do.
	"""
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You do not have permission to read {0}.").format(doctype), frappe.PermissionError)

	meta = frappe.get_meta(doctype)
	fields = [
		{
			"fieldname": f.fieldname,
			"label": f.label,
			"type": f.fieldtype,
			"options": f.options,
			"required": bool(f.reqd),
		}
		for f in meta.fields
		if f.fieldtype not in LAYOUT_FIELDTYPES
	]
	permissions = {p: bool(frappe.has_permission(doctype, p)) for p in ("read", "write", "create", "delete")}
	return {"doctype": doctype, "fields": fields, "permissions": permissions}


@tool
def query(
	doctype: str,
	filters: dict | None = None,
	fields: list[str] | None = None,
	limit: int = 20,
	order_by: str | None = None,
) -> list[dict]:
	"""Read records from a DocType, honouring the user's permissions.

	`filters` is a dict like {"status": "Open"} or {"qty": [">", 5]}. `fields` defaults
	to the record name. Returns a list of matching records (capped at 200).
	"""
	limit = min(max(int(limit), 1), MAX_QUERY_LIMIT)
	return frappe.get_list(
		doctype,
		filters=filters,
		fields=fields or ["name"],
		limit=limit,
		order_by=order_by,
	)


@tool
def execute(code: str) -> Any:
	"""Run Python in the Frappe sandbox to read or change data.

	`frappe` and `frappe.utils` are available; imports and file access are not. Assign
	the value you want returned to a variable named `result`. Writes run as the current
	user and enforce permissions. Confirm with the user via ask_user before changing data.
	"""
	exec_globals, _locals = safe_exec(code, script_filename="ai_execute")
	return exec_globals.get("result")


@tool
def ask_user(prompt: str, options: list[str] | None = None, multi_select: bool = False) -> Question:
	"""Ask the user a question and pause until they answer.

	Provide `options` for a single- or multi-select (an "Other" free-text choice is always
	offered). Use this to gather a decision or missing detail, or to confirm before acting.
	"""
	return Question(prompt=prompt, options=options or [], multi_select=multi_select)


BUILTIN_TOOLS: list[Tool] = [introspect, query, execute, ask_user]


def sync_builtin_tools() -> None:
	"""Register the builtin tools as AI Tool rows so agents can reference them."""
	for builtin in BUILTIN_TOOLS:
		if frappe.db.exists("AI Tool", builtin.name):
			continue
		frappe.get_doc(
			{
				"doctype": "AI Tool",
				"slug": builtin.name,
				"title": builtin.name.replace("_", " ").title(),
				"kind": "Module",
				"import_path": f"frappe.ai.tools.builtins.{builtin.name}",
				"description": builtin.description,
			}
		).insert()
