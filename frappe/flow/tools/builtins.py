# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
import re
from typing import Any, Literal

import frappe
from frappe import _

from flow.lib.tool import Tool, ToolContext, tool
from flow.utils.safe_exec import safe_exec

MAX_READ_LIMIT = 200
LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading"})
_CONFIRM_STR_LIMIT = 120
_ERROR_LIMIT = 300
_LIFECYCLE_BY_DOCSTATUS = {0: "submit", 1: "cancel", 2: "amend"}
SOURCE_TOOL_SLUGS = frozenset({"read", "grep"})
SUBAGENT_TOOL_SLUG = "subagent"
SERVER_TOOL_SLUGS = SOURCE_TOOL_SLUGS | {SUBAGENT_TOOL_SLUG}


def _server_only_tool() -> None:
	raise RuntimeError("This tool runs on the Flow server")


@tool
def read(path: str, offset: int | None = None, limit: int | None = None, *, ctx: ToolContext) -> str:
	"""Read a text or image file from the source of an app installed on this site."""
	_server_only_tool()


@tool
def grep(pattern: str, path: str = ".", include: str | None = None, *, ctx: ToolContext) -> str:
	"""Search installed app source files for a regular-expression pattern."""
	_server_only_tool()


@tool
def subagent(
	task: str,
	description: str,
	agent: str | None = None,
	subagent_id: str | None = None,
	*,
	ctx: ToolContext,
) -> str:
	"""Hand a self-contained task to a sub-agent with a fresh context and get back only its final answer."""
	_server_only_tool()


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
def find_doctypes(
	search: str | None = None, module: str | None = None, limit: int = 40, *, ctx: ToolContext
) -> list[dict]:
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
def describe(
	doctype: str, name: str | None = None, parent_doctype: str | None = None, *, ctx: ToolContext
) -> dict[str, Any]:
	"""Inspect a DocType's fields and your permissions. Pass `name` to also get a record's available actions.

	For a child table used by more than one DocType, pass the one you mean as `parent_doctype`.
	"""
	parent_doctype = _parent_doctype(doctype, parent_doctype)
	if not frappe.has_permission(doctype, "read", parent_doctype=parent_doctype):
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
	permissions = {
		p: bool(frappe.has_permission(doctype, p, parent_doctype=parent_doctype))
		for p in ("read", "write", "create", "delete")
	}
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
def read_records(
	doctype: str,
	filters: dict | None = None,
	fields: list[str] | None = None,
	limit: int = 20,
	order_by: str | None = None,
	parent_doctype: str | None = None,
	*,
	ctx: ToolContext,
) -> list[dict]:
	"""Read records from a DocType, honouring the user's permissions.

	`filters` is a dict like {"status": "Open"} or {"qty": [">", 5]}. `fields` defaults
	to the record name. Returns a list of matching records (capped at 200).
	A single DocType returns its one record, with every field unless `fields` is given.
	For a child table used by more than one DocType, pass the one you mean as `parent_doctype`.
	"""
	if frappe.get_meta(doctype).issingle:
		return [_read_single(doctype, fields)]
	limit = min(max(int(limit), 1), MAX_READ_LIMIT)
	if parent_doctype := _parent_doctype(doctype, parent_doctype):
		# frappe matches child rows to parents by name only
		filters = {**(filters or {}), "parenttype": parent_doctype}
	return frappe.get_list(
		doctype,
		filters=filters,
		fields=fields or ["name"],
		limit=limit,
		order_by=order_by,
		parent_doctype=parent_doctype,
	)


def _read_single(doctype: str, fields: list[str] | None) -> dict[str, Any]:
	"""A Single's values as its form shows them to this user."""
	doc = frappe.get_doc(doctype)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	values = doc.as_dict(no_nulls=True)
	return {f: values.get(f) for f in fields} if fields else values


def _parent_doctype(doctype: str, given: str | None) -> str | None:
	"""The DocType a child table is read through: the one given, else its only parent."""
	if not frappe.get_meta(doctype).istable:
		return None
	if given:
		return given
	table = {"fieldtype": ["in", frappe.model.table_fields], "options": doctype}
	parents = sorted(
		set(frappe.get_all("DocField", filters=table, pluck="parent"))
		| set(frappe.get_all("Custom Field", filters=table, pluck="dt"))
	)
	if len(parents) != 1:
		raise ValueError(
			f"{doctype} is a child table; pass parent_doctype, one of: {', '.join(parents) or 'none'}"
		)
	return parents[0]


@tool(
	background=lambda args: bool(
		frappe.db.get_value("Report", {"name": args.get("report_name")}, "prepared_report")
	)
)
def run_report(
	report_name: str,
	filters: dict | None = None,
	limit: int = 20,
	*,
	ctx: ToolContext,
) -> dict[str, Any]:
	"""Run a Query or Script report, such as General Ledger, honouring the user's permissions.

	Find names with read_records("Report", {"name": ["like", "%ledger%"]}, ["name", "ref_doctype"]),
	or by the DocType a report covers, {"ref_doctype": "Sales Invoice"}.
	`filters` is a dict like {"company": "Acme", "from_date": "2026-01-01"}; a failed or empty run
	lists the filters it can find (may be incomplete). Returns the columns, the full row count, the report's total row if
	it has one, and up to `limit` rows (capped at 200). To work over more rows, run the report inside execute with
	frappe.call("frappe.desk.query_report.run", report_name=..., filters=..., ignore_prepared_report=True) and return
	only what you need, such as totals or the top rows.
	"""
	from frappe.desk.query_report import get_report_doc, run

	report = get_report_doc(report_name)  # raises if missing, forbidden or disabled
	if report.report_type == "Report Builder":
		raise ValueError(f"{report_name} is a Report Builder report; read its DocType with read_records.")
	# a failing query report breaks the transaction
	if report.report_type == "Query Report":
		given = filters or report.custom_filters or {}
		if missing := set(re.findall(r"%\((\w+)\)s", report.query or "")) - set(given):
			raise ValueError(f"Missing filters: {', '.join(sorted(missing))}")
	limit = min(max(int(limit), 1), MAX_READ_LIMIT)
	try:
		# saved filters apply only when none are passed
		data = run(
			report_name, filters=filters or {}, ignore_prepared_report=True, are_default_filters=not filters
		)
	except Exception as e:
		cause = e
		if isinstance(e, frappe.InReadOnlyMode):  # frappe's failure log hid the report's error
			while cause.__context__:
				cause = cause.__context__
		raise ValueError(f"{_error_text(cause)}\nThe report's filters {_report_filters(report_name)}") from e

	fieldnames = [c["fieldname"] for c in data["columns"]]
	columns = [
		{"fieldname": c["fieldname"], "label": c.get("label")} for c in data["columns"] if not c.get("hidden")
	]
	rows = data["result"] or []
	total_row = rows[-1] if data.get("add_total_row") and rows else None
	row_count = len(rows) - 1 if total_row is not None else len(rows)
	# count and total before the rows, so a cut keeps them
	result: dict[str, Any] = {"columns": columns, "row_count": row_count}
	if total_row is not None:
		result["total_row"] = _report_row(total_row, fieldnames, columns)
	result["rows"] = [_report_row(row, fieldnames, columns) for row in rows[: min(limit, row_count)]]
	if not row_count:
		result["available_filters"] = _report_filters(report_name)
	return result


def _report_row(row: Any, fieldnames: list[str], columns: list[dict]) -> dict[str, Any]:
	"""A row keyed by fieldname, shown columns only; the total row arrives as a list."""
	cells = row if isinstance(row, dict) else dict(zip(fieldnames, row, strict=True))
	return {c["fieldname"]: cells.get(c["fieldname"]) for c in columns}


def _report_filters(report_name: str) -> str:
	"""Filter fieldnames from the report's Report Filter rows and its JS."""
	from frappe.desk.query_report import get_script

	script = get_script(report_name)
	names = [f.fieldname + ("*" if f.mandatory else "") for f in script["filters"]]
	# a JS filter runs to the next fieldname
	parts = re.split(r"""fieldname["']?\s*:\s*["'](\w+)""", script["script"])
	names += [
		name + ("*" if re.search(r"""reqd["']?\s*:\s*(1|true)""", rest) else "")
		for name, rest in zip(parts[1::2], parts[2::2], strict=True)
	]
	# legend first; long errors get cut
	return "(* = required) " + ", ".join(dict.fromkeys(names)) if names else "none found (may be incomplete)"


KNOWLEDGE_SEARCH_SLUG = "search_knowledge"

_KNOWLEDGE_SEARCH_DESCRIPTION = """Search this agent's knowledge bases for passages relevant to `query`.

Use this to ground answers in the agent's curated knowledge before relying on your own. Returns the \
most relevant chunks, each with its text, similarity score, and source. The knowledge bases searched \
are fixed by the agent's configuration — you cannot choose, add, or widen them."""


def bind_search_knowledge(kbs: list[str]) -> Tool:
	"""Build a `search_knowledge` tool scoped to `kbs`. The model sees only `query`; the
	knowledge bases come from the agent's config and cannot be chosen or widened. The
	registered builtin binds an empty list, so an unbound call fails closed in `retrieve`."""

	def search_knowledge(query: str, *, ctx: ToolContext) -> list[dict[str, Any]]:
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


ATTACHMENT_SEARCH_SLUG = "search_attachments"

_ATTACHMENT_SEARCH_DESCRIPTION = """Search the files attached to this conversation for passages relevant to `query`.

Use it when the user asks about an attached file that was too large to show in full. Returns the \
most relevant chunks, each with its text, similarity score and file name."""


def bind_search_attachments(session: str | None) -> Tool:
	"""A `search_attachments` tool scoped to one session. Unbound (None), it finds nothing."""

	def search_attachments(query: str, *, ctx: ToolContext) -> list[dict[str, Any]]:
		from flow.knowledge.retriever import retrieve_attachments

		if not session:
			return []
		names = dict(
			frappe.get_all(
				"Flow Session Attachment",
				filters={"parent": session},
				fields=["file", "file_name"],
				as_list=True,
			)
		)
		return [
			{"file": names.get(hit["attachment"]), "content": hit["content"], "score": hit["score"]}
			for hit in retrieve_attachments(query, session=session)
		]

	return tool(search_attachments, description=_ATTACHMENT_SEARCH_DESCRIPTION)


search_attachments = bind_search_attachments(None)


_UPDATE_MEMORY_DESCRIPTION = """Save a durable fact to memory, or revise one by passing its memory_id.

Memories relevant to the user's message are shown with it in a <memory> block, with their ids, \
in this and future conversations. Save stable, reusable facts: identifiers and mappings (e.g. an \
invoice item name to its ERP item code), business rules, corrections the user gives you, and their \
preferences. Do not save transient conversation state, secrets, or anything you can re-derive by \
reading records. Write one short, self-contained, third-person fact per memory; when a fact \
changes, revise the shown memory instead of adding another.

scope:
- "agent" — true for everyone who uses this agent (mappings, business rules, conventions).
- "user" — specific to the current user (their preferences and defaults)."""


def bind_update_memory(agent: str | None, session: str | None = None) -> Tool:
	"""An `update_memory` tool bound to `agent` and `session`. Unbound (None), it refuses."""

	def update_memory(
		content: str,
		scope: Literal["agent", "user"],
		memory_id: str | None = None,
		*,
		ctx: ToolContext,
	) -> dict[str, Any]:
		from flow.memory.memory import save_memory

		if not agent:
			frappe.throw(_("Memory is not configured for this agent."), title=_("Memory Unavailable"))
		return save_memory(agent, content=content, scope=scope, memory_id=memory_id, session=session)

	return tool(update_memory, description=_UPDATE_MEMORY_DESCRIPTION)


update_memory = bind_update_memory(None)


SKILL_TOOL_SLUG = "load_skill"

_LOAD_SKILL_DESCRIPTION = """Load a skill's full instructions by name, then follow them.

The skills you can load are listed in the <available_skills> block of your instructions, each with \
a description of when it applies. When a task matches one, call this with that exact name before \
starting the task, and treat what you get back as authoritative for it."""


def bind_load_skill(agent: str | None) -> Tool:
	"""A `load_skill` tool scoped to `agent`'s skills. Unbound (None), it refuses."""

	def load_skill(name: str, *, ctx: ToolContext) -> str:
		if not agent:
			frappe.throw(_("Skills are not configured for this agent."), title=_("Skill Unavailable"))
		available = {row.name for row in frappe.get_doc("Flow Agent", agent).visible_skills()}
		if name not in available:
			frappe.throw(
				_("No skill named {0}. Available: {1}").format(name, ", ".join(sorted(available)) or "none"),
				title=_("Unknown Skill"),
			)
		return frappe.db.get_value("Flow Skill", name, "instructions")

	return tool(load_skill, description=_LOAD_SKILL_DESCRIPTION)


load_skill = bind_load_skill(None)


@tool(
	requires_confirmation=True,
	confirm_prompt=lambda args: (
		f"{args.get('description') or _('Run Python code')}:\n\n{args.get('code', '')}"
	),
)
def execute(code: str, description: str, *, ctx: ToolContext) -> Any:
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
	- Also: read_records, describe, find_doctypes, frappe.call (whitelisted methods), frappe.enqueue,
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
	exec_globals, _locals = safe_exec(code, script_filename="ai_execute", tool_context=ctx)
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
def create(doctype: str, records: list[dict[str, Any]], *, ctx: ToolContext) -> dict[str, Any]:
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
def update(doctype: str, names: list[str], values: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
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
def delete(doctype: str, names: list[str], *, ctx: ToolContext) -> dict[str, Any]:
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
	*,
	ctx: ToolContext,
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
	read_records,
	run_report,
	read,
	grep,
	subagent,
	search_knowledge,
	search_attachments,
	update_memory,
	load_skill,
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
					"background": int(builtin.background is True),
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
					"background": int(builtin.background is True),
				}
			).insert(ignore_permissions=True)
