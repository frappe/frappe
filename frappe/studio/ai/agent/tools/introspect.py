"""Introspection tools — let the agent read the data model and the page's data
state before wiring anything.

All are server-side: the loop runs the handler in the worker and feeds the
returned string back to the model. These are READS only — they never mutate the
page. They wrap the same whitelisted helpers the Studio data-source UI uses, so
the agent sees exactly what a human binding data would see.
"""

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.block_codec import BlockCodec

# Field metadata is verbose; the model only needs these keys to pick fields/filters.
_FIELD_KEYS = ("fieldname", "label", "fieldtype", "options")
# Cap list/search results so a huge site can't blow the context window.
_MAX_DOCTYPES = 40
_MAX_FIELDS = 80


def run_get_page_state(ctx, args: dict) -> str:
	"""A compact snapshot of the page's DATA wiring — existing data sources,
	variables, and whether a page script is set. The block tree itself is already
	in the conversation context, so it is not repeated here."""
	page = frappe.get_doc("Studio Page", ctx.page_id) if ctx.page_id else None
	if page is None:
		return "No page in context."

	sources = [
		{
			"name": r.resource_name,
			"type": r.resource_type,
			"doctype": r.document_type or None,
		}
		for r in (page.resources or [])
	]
	variables = [{"name": v.variable_name, "type": v.variable_type} for v in (page.variables or [])]
	state = {
		"data_sources": sources,
		"variables": variables,
		"has_page_script": bool((page.script or "").strip()),
	}
	return "Current page data state:\n" + BlockCodec.to_json(state)


def run_list_doctypes(ctx, args: dict) -> str:
	"""Search DocTypes the user can read, by name fragment. Excludes child tables
	(they can't back a Document List on their own)."""
	query = (args.get("query") or "").strip()
	filters = {"istable": 0}
	if query:
		filters["name"] = ["like", f"%{query}%"]
	names = frappe.get_all(
		"DocType",
		filters=filters,
		pluck="name",
		order_by="name asc",
		limit_page_length=_MAX_DOCTYPES * 2,
	)
	allowed = [n for n in names if frappe.has_permission(n, "read")][:_MAX_DOCTYPES]
	if not allowed:
		hint = f" matching '{query}'" if query else ""
		return f"No readable DocTypes found{hint}."
	return f"DocTypes (showing {len(allowed)}):\n" + BlockCodec.to_json(allowed)


def run_get_doctype_fields(ctx, args: dict) -> str:
	doctype = (args.get("doctype") or "").strip()
	if not doctype or not frappe.db.exists("DocType", doctype):
		return f"DocType '{doctype}' not found."
	if not frappe.has_permission(doctype, "read"):
		return f"You do not have read access to '{doctype}'."
	from studio.api import get_doctype_fields

	fields = get_doctype_fields(doctype)[:_MAX_FIELDS]
	trimmed = [{k: f.get(k) for k in _FIELD_KEYS if f.get(k)} for f in fields]
	return f"Fields of {doctype}:\n" + BlockCodec.to_json(trimmed)


def run_get_sort_fields(ctx, args: dict) -> str:
	doctype = (args.get("doctype") or "").strip()
	if not doctype or not frappe.db.exists("DocType", doctype):
		return f"DocType '{doctype}' not found."
	from studio.api import get_sort_fields

	fields = [{"fieldname": f["fieldname"], "label": f.get("label")} for f in get_sort_fields(doctype)]
	return f"Sortable fields of {doctype}:\n" + BlockCodec.to_json(fields)


def run_get_whitelisted_methods(ctx, args: dict) -> str:
	doctype = (args.get("doctype") or "").strip()
	if not doctype or not frappe.db.exists("DocType", doctype):
		return f"DocType '{doctype}' not found."
	from studio.api import get_whitelisted_methods

	methods = get_whitelisted_methods(doctype)
	if not methods:
		return f"{doctype} exposes no whitelisted document methods."
	return f"Whitelisted methods of {doctype}:\n" + BlockCodec.to_json(methods)


_DOCTYPE_PARAM = {
	"type": "object",
	"properties": {"doctype": {"type": "string", "description": "The DocType name."}},
	"required": ["doctype"],
}


get_page_state = Tool(
	name="get_page_state",
	side="server",
	handler=run_get_page_state,
	description=(
		"Read the page's current DATA wiring: the data sources already defined (name, type, "
		"doctype), the variables, and whether a page script exists. Call this first when a request "
		"involves showing or binding data, so you don't recreate a source that already exists. The "
		"block tree is already in your context — this covers only the data layer."
	),
	parameters={"type": "object", "properties": {}},
)

list_doctypes = Tool(
	name="list_doctypes",
	side="server",
	handler=run_list_doctypes,
	description=(
		"Find Frappe DocTypes by a name fragment (e.g. 'todo', 'sales order') to pick the one a "
		"data source should read from. Returns DocTypes the user can read. Use before add_data_source "
		"when you're unsure of the exact DocType name."
	),
	parameters={
		"type": "object",
		"properties": {
			"query": {
				"type": "string",
				"description": "Name fragment to search for. Omit to list the first readable DocTypes.",
			}
		},
	},
)

get_doctype_fields = Tool(
	name="get_doctype_fields",
	side="server",
	handler=run_get_doctype_fields,
	description=(
		"List a DocType's fields (fieldname, label, fieldtype, options) so you can choose which "
		"fields a Document-List data source should fetch and which to show in a table/list. Always "
		"call this before add_data_source so the 'fields' you request are real."
	),
	parameters=_DOCTYPE_PARAM,
)

get_sort_fields = Tool(
	name="get_sort_fields",
	side="server",
	handler=run_get_sort_fields,
	description="List the fields a Document-List data source can sort by (sort_field) for a DocType.",
	parameters=_DOCTYPE_PARAM,
)

get_whitelisted_methods = Tool(
	name="get_whitelisted_methods",
	side="server",
	handler=run_get_whitelisted_methods,
	description=(
		"List a DocType's whitelisted document methods — callable on a single-Document data source. "
		"Only needed for Document (single) sources that invoke server methods."
	),
	parameters=_DOCTYPE_PARAM,
)

TOOLS = [get_page_state, list_doctypes, get_doctype_fields, get_sort_fields, get_whitelisted_methods]
