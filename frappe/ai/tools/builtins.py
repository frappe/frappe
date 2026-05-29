# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.ai.tool import Tool, tool
from frappe.utils.safe_exec import safe_exec

MAX_READ_LIMIT = 200
LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading"})


@tool
def find_doctypes(search: str | None = None, module: str | None = None, limit: int = 40) -> list[dict]:
	"""Find exact DocType names before describe/read — never guess names.

	Search by keyword (substring of the name) and/or filter by module. Returns a list
	of {name, module} you can read. Child tables are excluded; single DocTypes are included.
	"""
	limit = min(max(int(limit), 1), MAX_READ_LIMIT)
	filters: dict[str, Any] = {"istable": 0}
	if module:
		filters["module"] = module
	if search:
		filters["name"] = ["like", f"%{search}%"]
	rows = frappe.get_all(
		"DocType", filters=filters, fields=["name", "module"], order_by="name", limit=limit
	)
	return [r for r in rows if frappe.has_permission(r["name"], "read")]


@tool
def describe(doctype: str) -> dict[str, Any]:
	"""Describe a DocType's schema before reading or acting on it.

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
def read(
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
	limit = min(max(int(limit), 1), MAX_READ_LIMIT)
	return frappe.get_list(
		doctype,
		filters=filters,
		fields=fields or ["name"],
		limit=limit,
		order_by=order_by,
	)


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: f"Run this Python:\n\n{args.get('code', '')}",
)
def execute(code: str) -> Any:
	"""Run Python in the Frappe sandbox (RestrictedPython) for computation, emails, or multi-record work.

	Assign the value you want returned to a variable named `result`.
	Example:
	    result = frappe.db.count("ToDo", {"status": "Open"})

	Sandbox limits — code using these FAILS:
	- No `import`. `frappe` and `frappe.utils` are already in scope; nothing else can be imported.
	- No names or attributes starting with `_` (no dunders, no `obj._private`).
	- Unavailable builtins: open, eval, exec, compile, getattr, setattr, hasattr,
	  globals, locals, vars, dir, type, input. Available: len, range, str, int, float,
	  bool, sum, sorted, enumerate, zip, min, max, abs, dict, list, set, tuple.
	- `str.format()` / `.format_map()` are blocked — use f-strings or `%` formatting.
	- `frappe.db.sql` is read-only (SELECT/EXPLAIN only).
	- `print()` output is logged, not returned — put what you want back into `result`.

	Writes run as the current user and enforce permissions. The user approves each call before it runs.
	"""
	exec_globals, _locals = safe_exec(code, script_filename="ai_execute")
	return exec_globals.get("result")


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		f"Create new {args.get('doctype', '?')}:\n\n"
		f"{json.dumps(args.get('values') or {}, indent=2, default=str)}"
	),
)
def create(doctype: str, values: dict[str, Any]) -> dict[str, Any]:
	"""Create a new record of `doctype` with the given field values.

	Use describe() first to discover required fields. Returns the new record's
	name. Respects the user's create permission and the doctype's validation.
	"""
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(
			_("You do not have permission to create {0}.").format(doctype), frappe.PermissionError
		)
	doc = frappe.new_doc(doctype)
	doc.update(values or {})
	doc.insert()
	return {"name": doc.name, "doctype": doctype}


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		f"Update {args.get('doctype', '?')} {args.get('name', '?')}:\n\n"
		f"{json.dumps(args.get('values') or {}, indent=2, default=str)}"
	),
)
def update(doctype: str, name: str, values: dict[str, Any]) -> dict[str, Any]:
	"""Update fields on an existing record.

	`values` is a dict of fieldname → new value. Runs the doctype's full validation.
	Respects the user's write permission on the specific record.
	"""
	if not frappe.has_permission(doctype, "write", name):
		frappe.throw(
			_("You do not have permission to update {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
	doc = frappe.get_doc(doctype, name)
	doc.update(values or {})
	doc.save()
	return {"name": doc.name, "doctype": doctype}


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: f"Delete {args.get('doctype', '?')} {args.get('name', '?')}",
)
def delete(doctype: str, name: str) -> dict[str, Any]:
	"""Delete a record.

	Respects the user's delete permission on the specific record. Fails if any other
	record links to this one (Frappe's link integrity check).
	"""
	if not frappe.has_permission(doctype, "delete", name):
		frappe.throw(
			_("You do not have permission to delete {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
	frappe.delete_doc(doctype, name, ignore_missing=False)
	return {"deleted": True, "doctype": doctype, "name": name}


BUILTIN_TOOLS: list[Tool] = [find_doctypes, describe, read, create, update, delete, execute]


def sync_builtin_tools() -> None:
	"""Register the builtin tools as AI Tool rows so agents can reference them."""
	for builtin in BUILTIN_TOOLS:
		if frappe.db.exists("AI Tool", builtin.name):
			current = frappe.db.get_value(
				"AI Tool",
				builtin.name,
				["is_system_generated", "requires_confirmation", "description"],
				as_dict=True,
			)
			if not current.is_system_generated:
				frappe.db.set_value("AI Tool", builtin.name, "is_system_generated", 1)
			if bool(current.requires_confirmation) != builtin.requires_confirmation:
				frappe.db.set_value(
					"AI Tool", builtin.name, "requires_confirmation", int(builtin.requires_confirmation)
				)
			if current.description != builtin.description:
				frappe.db.set_value("AI Tool", builtin.name, "description", builtin.description)
			continue
		frappe.get_doc(
			{
				"doctype": "AI Tool",
				"slug": builtin.name,
				"title": builtin.name.replace("_", " ").title(),
				"kind": "Module",
				"import_path": f"frappe.ai.tools.builtins.{builtin.name}",
				"description": builtin.description,
				"is_system_generated": 1,
				"requires_confirmation": int(builtin.requires_confirmation),
			}
		).insert()
