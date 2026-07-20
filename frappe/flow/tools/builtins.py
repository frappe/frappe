# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import Any, Literal

import frappe
from frappe import _

from flow.lib.tool import Tool, tool
from flow.utils.safe_exec import safe_exec

MAX_READ_LIMIT = 200
LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading"})
_CONFIRM_STR_LIMIT = 120
_ERROR_LIMIT = 300
_LIFECYCLE_BY_DOCSTATUS = {0: "submit", 1: "cancel", 2: "amend"}


def _summarize_values(values: dict) -> str:
	"""Truncate long values for confirm prompts — keeps the display scannable."""
	display = {}
	for k, v in (values or {}).items():
		if isinstance(v, str) and len(v) > _CONFIRM_STR_LIMIT:
			display[k] = v[:_CONFIRM_STR_LIMIT] + f"… ({len(v)} chars)"
		elif isinstance(v, list) and len(v) > 6:
			display[k] = [*v[:6], f"… +{len(v) - 6} more"]
		else:
			display[k] = v
	return json.dumps(display, indent=2, default=str, ensure_ascii=False)


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
	rows = frappe.get_all("DocType", filters=filters, fields=["name", "module"], order_by="name", limit=limit)
	return [r for r in rows if frappe.has_permission(r["name"], "read")]


@tool
def describe(doctype: str, name: str | None = None) -> dict[str, Any]:
	"""Inspect a DocType's fields and your permissions. Pass `name` to also get a record's available actions."""
	if not frappe.has_permission(doctype, "read"):
		raise PermissionError(f"No permission to read {doctype}")

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
	result: dict[str, Any] = {"doctype": doctype, "fields": fields, "permissions": permissions}

	if name:
		if not frappe.has_permission(doctype, "read", name):
			raise PermissionError(f"No permission to read {doctype} {name}")
		doc = frappe.get_doc(doctype, name)
		result["name"] = doc.name
		result["docstatus"] = int(doc.docstatus)
		result["actions"] = _doc_actions(doc, meta)
	return result


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


KNOWLEDGE_SEARCH_SLUG = "search_knowledge"

_KNOWLEDGE_SEARCH_DESCRIPTION = """Search this agent's knowledge bases for passages relevant to `query`.

Use this to ground answers in the agent's curated knowledge before relying on your own. Returns the \
most relevant chunks, each with its text, similarity score, and source. The knowledge bases searched \
are fixed by the agent's configuration — you cannot choose, add, or widen them."""


def bind_search_knowledge(kbs: list[str]) -> Tool:
	"""Build a `search_knowledge` tool scoped to `kbs`. The model sees only `query`; the
	knowledge bases come from the agent's config and cannot be chosen or widened. The
	registered builtin binds an empty list, so an unbound call fails closed in `retrieve`."""

	def search_knowledge(query: str) -> list[dict[str, Any]]:
		from flow.knowledge.retriever import retrieve

		return retrieve(query, kbs=kbs)

	return tool(search_knowledge, description=_knowledge_search_description(kbs))


def _knowledge_search_description(kbs: list[str]) -> str:
	"""Append the bound knowledge bases' descriptions so the model knows what's searchable
	and when to call the tool."""
	if not kbs:
		return _KNOWLEDGE_SEARCH_DESCRIPTION
	rows = frappe.get_all(
		"Flow Knowledge Base",
		filters={"name": ["in", kbs], "enabled": 1},
		fields=["title", "description"],
	)
	listed = "\n".join(f"- {r.title}: {r.description}" for r in rows if r.description)
	if not listed:
		return _KNOWLEDGE_SEARCH_DESCRIPTION
	return f"{_KNOWLEDGE_SEARCH_DESCRIPTION}\n\nThis agent's knowledge bases:\n{listed}"


search_knowledge = bind_search_knowledge([])


_UPDATE_MEMORY_DESCRIPTION = """Save a durable fact to persistent memory, or edit one by passing its memory_id.

Saved memories appear in the <agent_memory> block of your system prompt on every turn, \
including future conversations.

When to save: stable, reusable facts learned during the conversation — mappings and \
identifiers (e.g. an invoice item name to its ERP item code), business rules, corrections \
the user gives you, and their preferences. Do not save transient conversation state, \
secrets or credentials, or anything you can re-derive by reading records.

How to write: one short, self-contained, third-person fact per memory. Before adding, \
check <agent_memory> — if a related memory exists, pass its memory_id to revise or extend \
it instead of adding a duplicate. When a fact changes, edit the existing memory to the new \
value. Near the memory limit, consolidate related memories into one.

scope:
- "agent" — true for everyone who uses this agent (mappings, business rules, conventions).
- "user" — specific to the current user (their preferences and defaults).
Ask: is this about the organisation, or about this person?

keywords: optional space-separated search terms that help this memory resurface later — \
synonyms, alternate names, codes, or the words a user would ask with (e.g. for a fact about \
stationery tax: "pens paper pencils office supplies GST"). They are used only for retrieval, \
never shown as part of the fact. Add them when the fact's wording differs from how it will be \
asked about."""


def bind_update_memory(agent: str | None) -> Tool:
	"""Build an `update_memory` tool bound to `agent`. The binding comes from the agent's
	config, never the model. The registered builtin binds None, so an unbound call
	fails closed."""

	def update_memory(
		content: str,
		scope: Literal["agent", "user"],
		memory_id: str | None = None,
		keywords: str | None = None,
	) -> dict[str, Any]:
		from flow.memory.memory import save_memory

		if not agent:
			frappe.throw(_("Memory is not configured for this agent."), title=_("Memory Unavailable"))
		return save_memory(agent, content=content, scope=scope, memory_id=memory_id, keywords=keywords)

	return tool(update_memory, description=_UPDATE_MEMORY_DESCRIPTION)


update_memory = bind_update_memory(None)


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		f"{args.get('description') or _('Run Python code')}:\n\n{args.get('code', '')}"
	),
)
def execute(code: str, description: str) -> Any:
	"""Run Python in a permission-respecting sandbox for computation, emails, or multi-record work.

	`description` is one short, plain-English sentence stating what this code does, for a
	non-technical user who approves it — e.g. "Count open ToDos". Describe the intent, not the code.

	Do NOT write `import` statements — imports are blocked and the whole script fails. `frappe`
	and `frappe.utils` are already in scope; everything you can use is listed below, so never
	start with `import ...`.

	Every function here enforces the current user's permissions — there is no way to read or
	write data the user cannot access. Assign the value to return to a variable named `result`.
	Example (no imports, just use `frappe` directly):
	    result = frappe.db.count("ToDo", {"status": "Open"})

	Available:
	- Reads: frappe.get_list (supports group_by and aggregates via dict fields, e.g.
	  fields=[{"SUM": "qty", "as": "total"}] or [{"COUNT": "*", "as": "n"}]),
	  frappe.get_doc (returns a dict), frappe.get_meta, frappe.db.get_value/get_single_value/count/exists.
	- Writes: create, update, delete, run_action — the same permission-checked tools you call directly.
	- Also: read, describe, find_doctypes, frappe.call (whitelisted methods), frappe.enqueue,
	  frappe.sendmail, frappe.get_print, frappe.utils.* (dates, numbers, strings).

	Sandbox limits — code using these FAILS:
	- No `import`. `frappe` and `frappe.utils` are already in scope; nothing else can be imported.
	- No names or attributes starting with `_` (no dunders, no `obj._private`).
	- No raw database access: frappe.db.sql, frappe.qb, frappe.db.set_value and frappe.get_all are
	  unavailable — use frappe.get_list and the write tools, which respect permissions.
	- Unavailable builtins: open, eval, exec, compile, getattr, setattr, hasattr,
	  globals, locals, vars, dir, type, input. Available: len, range, str, int, float,
	  bool, sum, sorted, enumerate, zip, min, max, abs, dict, list, set, tuple.
	- `str.format()` / `.format_map()` are blocked — use f-strings or `%` formatting.
	- `print()` output is logged, not returned — put what you want back into `result`.

	The user approves each call before it runs.
	"""
	exec_globals, _locals = safe_exec(code, script_filename="ai_execute")
	return exec_globals.get("result")


def _error_text(e: Exception) -> str:
	"""Some frappe exceptions carry their message in the message log, not str() — fall back to the type."""
	return (str(e).strip() or e.__class__.__name__)[:_ERROR_LIMIT]


def _summarize_names(names: list[str] | None, limit: int = 6) -> str:
	names = names or []
	shown = ", ".join(str(n) for n in names[:limit])
	if len(names) > limit:
		shown += f" … +{len(names) - limit} more"
	return shown or "—"


def _doc_actions(doc: Any, meta: Any) -> dict[str, Any]:
	"""Actions the current user can run on this record: lifecycle, workflow, methods."""
	lifecycle: list[str] = []
	if getattr(meta, "is_submittable", 0):
		lifecycle.append(_LIFECYCLE_BY_DOCSTATUS.get(int(doc.docstatus)))
	if int(doc.docstatus) != 1 and frappe.has_permission(doc.doctype, "delete", doc.name):
		lifecycle.append("delete")
	if getattr(meta, "allow_rename", 0):
		lifecycle.append("rename")
	return {
		"lifecycle": [a for a in lifecycle if a],
		"workflow": sorted(_workflow_actions(doc)),
		"methods": _whitelisted_methods(doc.doctype),
	}


def _workflow_actions(doc: Any) -> set[str]:
	from frappe.model.workflow import get_transitions, get_workflow_name

	if not get_workflow_name(doc.doctype):
		return set()
	try:
		return {t.get("action") for t in get_transitions(doc) if t.get("action")}
	except Exception:
		return set()


def _whitelisted_methods(doctype: str) -> list[str]:
	"""Custom whitelisted controller methods (the app-specific form buttons), excluding base Document methods."""
	from frappe.model.base_document import get_controller
	from frappe.model.document import Document

	try:
		controller = get_controller(doctype)
	except Exception:
		return []
	base = set(dir(Document))
	methods = set()
	for attr_name in dir(controller):
		if attr_name.startswith("_") or attr_name in base:
			continue
		attr = getattr(controller, attr_name, None)
		if callable(attr) and getattr(attr, "__func__", attr) in frappe.whitelisted:
			methods.add(attr_name)
	return sorted(methods)


def _resolve_method(doc: Any, action: str) -> Any:
	method = getattr(doc, action, None)
	if callable(method) and getattr(method, "__func__", method) in frappe.whitelisted:
		return method
	return None


def _apply_action(doctype: str, name: str, action: str, args: dict[str, Any]) -> Any:
	doc = frappe.get_doc(doctype, name)
	if action == "submit":
		doc.submit()
		return {"name": doc.name, "docstatus": int(doc.docstatus)}
	if action == "cancel":
		doc.cancel()
		return {"name": doc.name, "docstatus": int(doc.docstatus)}
	if action == "amend":
		amended = frappe.copy_doc(doc)
		amended.amended_from = doc.name
		amended.insert()
		return {"name": amended.name}
	if action in _workflow_actions(doc):
		from frappe.model.workflow import apply_workflow

		apply_workflow(doc, action)
		return {"name": doc.name, "action": action}
	if _resolve_method(doc, action) is not None:
		return doc.run_method(action, **args)
	raise ValueError(f"Unknown action {action!r} for {doctype}")


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		_("Create {0} {1} record(s):\n\n{2}").format(
			len(args.get("records") or []),
			args.get("doctype", "?"),
			_summarize_values((args.get("records") or [{}])[0]),
		)
	),
)
def create(doctype: str, records: list[dict[str, Any]]) -> dict[str, Any]:
	"""Create one or more records. `records` is a list of field-value dicts, each validated and inserted."""
	if not frappe.has_permission(doctype, "create"):
		raise PermissionError(f"No permission to create {doctype}")

	created: list[str] = []
	failures: list[dict[str, Any]] = []
	for row, values in enumerate(records):
		try:
			doc = frappe.new_doc(doctype)
			doc.update(values or {})
			doc.insert()
			created.append(doc.name)
		except Exception as e:
			failures.append({"row": row, "error": _error_text(e)})

	result: dict[str, Any] = {"doctype": doctype, "created": created}
	if failures:
		result["failures"] = failures
	return result


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		_("Update {0} {1} ({2}):\n\n{3}").format(
			len(args.get("names") or []),
			args.get("doctype", "?"),
			_summarize_names(args.get("names")),
			_summarize_values(args.get("values")),
		)
	),
)
def update(doctype: str, names: list[str], values: dict[str, Any]) -> dict[str, Any]:
	"""Apply the same field values to one or more existing records. Runs full validation per record."""
	updated: list[str] = []
	failures: list[dict[str, Any]] = []
	for name in names:
		try:
			if not frappe.has_permission(doctype, "write", name):
				raise frappe.PermissionError(_("No permission to update {0} {1}.").format(doctype, name))
			doc = frappe.get_doc(doctype, name)
			doc.update(values or {})
			doc.save()
			updated.append(doc.name)
		except Exception as e:
			failures.append({"name": name, "error": _error_text(e)})

	result: dict[str, Any] = {"doctype": doctype, "updated": updated}
	if failures:
		result["failures"] = failures
	return result


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		_("Delete {0} {1}: {2}").format(
			len(args.get("names") or []),
			args.get("doctype", "?"),
			_summarize_names(args.get("names")),
		)
	),
)
def delete(doctype: str, names: list[str]) -> dict[str, Any]:
	"""Delete one or more records. Fails per record if another record links to it."""
	deleted: list[str] = []
	failures: list[dict[str, Any]] = []
	for name in names:
		try:
			if not frappe.has_permission(doctype, "delete", name):
				raise frappe.PermissionError(_("No permission to delete {0} {1}.").format(doctype, name))
			frappe.delete_doc(doctype, name, ignore_missing=False)
			deleted.append(name)
		except Exception as e:
			failures.append({"name": name, "error": _error_text(e)})

	result: dict[str, Any] = {"doctype": doctype, "deleted": deleted}
	if failures:
		result["failures"] = failures
	return result


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		_("Run '{0}' on {1} {2}: {3}").format(
			args.get("action"),
			len(args.get("names") or []),
			args.get("doctype", "?"),
			_summarize_names(args.get("names")),
		)
	),
)
def run_action(
	doctype: str,
	names: list[str],
	action: str,
	args: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Run a document action found via describe: submit, cancel, amend, rename, a workflow transition, or a whitelisted method."""
	args = args or {}

	if action == "rename":
		if len(names) != 1:
			raise ValueError("rename acts on a single document; pass exactly one name.")
		new_name = args.get("new_name")
		if not new_name:
			raise ValueError("rename requires args.new_name.")
		return {"action": "rename", "old": names[0], "new": frappe.rename_doc(doctype, names[0], new_name)}

	results: list[dict[str, Any]] = []
	failures: list[dict[str, Any]] = []
	for name in names:
		try:
			results.append({"name": name, "result": _apply_action(doctype, name, action, args)})
		except Exception as e:
			failures.append({"name": name, "error": _error_text(e)})

	result: dict[str, Any] = {"action": action, "results": results}
	if failures:
		result["failures"] = failures
	return result


BUILTIN_TOOLS: list[Tool] = [
	find_doctypes,
	describe,
	read,
	search_knowledge,
	update_memory,
	create,
	update,
	delete,
	run_action,
	execute,
]


def sync_builtin_tools() -> None:
	"""Upsert builtin tools as Flow Tool rows. Uses db.set_value to bypass the immutability
	guard in FlowTool.validate (which protects user edits, not system migration)."""
	for builtin in BUILTIN_TOOLS:
		import_path = f"flow.tools.builtins.{builtin.name}"
		if frappe.db.exists("Flow Tool", builtin.name):
			frappe.db.set_value(
				"Flow Tool",
				builtin.name,
				{
					"import_path": import_path,
					"description": builtin.description,
					"requires_confirmation": int(builtin.requires_confirmation),
					"is_system_generated": 1,
				},
			)
		else:
			frappe.get_doc(
				{
					"doctype": "Flow Tool",
					"slug": builtin.name,
					"title": builtin.name.replace("_", " ").title(),
					"type": "Imported",
					"import_path": import_path,
					"description": builtin.description,
					"is_system_generated": 1,
					"requires_confirmation": int(builtin.requires_confirmation),
				}
			).insert(ignore_permissions=True)
