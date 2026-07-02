"""Data-source tools — full CRUD over a page's data sources.

A "data source" is the AI/UX-facing name for a `Studio Page Resource` child row
(backing table: `resources`). These tools are server-side: the loop runs the
handler in the worker, which mutates the `Studio Page` doc and saves it. Saving a
standard page auto-exports its JSON (`on_update`). After a successful write the
handler commits and emits a `reload` event so the canvas re-fetches resources and
live `{{ <name>.data }}` bindings start resolving.

Block edits (ListView/Repeater + bind_prop) are CLIENT tools applied on the
canvas; add the data source FIRST, then lay out and bind the blocks — that order
keeps the canvas block edits from racing this save.
"""

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import dangling_binding_warning, load_page, save_page, text_arg
from studio.ai.block_codec import BlockCodec

RESOURCE_TYPES = ("Document List", "Document", "API Resource")
# Resource child-table fields that hold JSON; serialized before assignment so the
# value round-trips regardless of dict/list shape.
_JSON_FIELDS = ("fields", "filters", "params", "whitelisted_methods")


def run_add_data_source(ctx, args: dict) -> str:
	name = text_arg(args.get("data_source_name"))
	source_type = text_arg(args.get("data_source_type"))
	if not name:
		return "FAILED: data_source_name is required."
	if source_type not in RESOURCE_TYPES:
		return f"FAILED: data_source_type must be one of {list(RESOURCE_TYPES)}."

	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if _find_resource(page, name):
		return f"FAILED: a data source named '{name}' already exists. Use update_data_source to change it."

	row = _build_row(name, source_type, args)
	if error := _validate_row(source_type, row):
		return f"FAILED: {error}"

	page.append("resources", row)
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)
	return f"Added {source_type} data source '{name}'. Bind blocks to it with {{{{ {name}.data }}}}."


def run_list_data_sources(ctx, args: dict) -> str:
	page = load_page(ctx)
	if page is None:
		return "No page in context."
	if not page.resources:
		return "No data sources defined on this page yet."
	out = [_describe_resource(r) for r in page.resources]
	return f"{len(out)} data source(s):\n" + BlockCodec.to_json(out)


def run_update_data_source(ctx, args: dict) -> str:
	name = text_arg(args.get("data_source_name"))
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	row = _find_resource(page, name)
	if row is None:
		return f"FAILED: no data source named '{name}'. Call list_data_sources to see the current set."

	changed = _apply_changes(row, args)
	if not changed:
		return "Nothing to update — pass the fields you want to change."
	if error := _validate_row(row.resource_type, row):
		return f"FAILED: {error}"
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)
	return f"Updated data source '{name}' ({', '.join(changed)})."


def run_delete_data_source(ctx, args: dict) -> str:
	name = text_arg(args.get("data_source_name"))
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	row = _find_resource(page, name)
	if row is None:
		return f"FAILED: no data source named '{name}'."

	page.resources.remove(row)
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)

	warning = dangling_binding_warning(ctx, name)
	return f"Deleted data source '{name}'." + (f" {warning}" if warning else "")


# --- row construction -----------------------------------------------------

# Resource child-table fields the tools can set. Tool arg names are chosen to match
# these fieldnames 1:1; the two renamed args (data_source_name/_type → resource_name/
# _type) are set directly in _build_row, so they're not listed here.
_RESOURCE_FIELDS = (
	"document_type",
	"document_name",
	"fetch_document_using_filters",
	"fields",
	"filters",
	"limit",
	"sort_field",
	"sort_order",
	"whitelisted_methods",
	"url",
	"method",
	"params",
	"transform",
	"on_success",
	"on_error",
	"auto",
)


def _build_row(name: str, source_type: str, args: dict) -> dict:
	row = {"resource_name": name, "resource_type": source_type}
	for field in _RESOURCE_FIELDS:
		if args.get(field) is not None:
			row[field] = _coerce(field, args[field])
	return row


def _apply_changes(row, args: dict) -> list[str]:
	"""Mutate an existing child row in place with the provided fields. Returns the
	list of fields that changed (for the result message)."""
	changed = []
	for field in _RESOURCE_FIELDS:
		if args.get(field) is not None:
			setattr(row, field, _coerce(field, args[field]))
			changed.append(field)
	return changed


def _coerce(field: str, value):
	"""JSON-typed fields are stored as strings; serialize dict/list inputs."""
	if field in _JSON_FIELDS and isinstance(value, dict | list):
		return frappe.as_json(value, indent=None)
	return value


def _validate_row(source_type: str, row) -> str | None:
	"""Cheap pre-checks mirroring Studio Page.validate_resources, so the model gets
	a precise correction instead of a raw save traceback."""
	get = row.get if isinstance(row, dict) else (lambda k: getattr(row, k, None))
	if source_type in ("Document", "Document List") and not get("document_type"):
		return "document_type is required for Document and Document List sources."
	if source_type == "Document List" and _is_empty(get("fields")):
		return "Document List needs 'fields' — a non-empty list of fieldnames to fetch."
	if source_type == "Document" and not get("fetch_document_using_filters") and not get("document_name"):
		return "Document source needs either document_name or fetch_document_using_filters with filters."
	if source_type == "API Resource" and not get("url"):
		return "API Resource needs a url."
	return None


def _is_empty(value) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return value.strip() in ("", "[]", "{}")
	return not value


# --- resource-specific helpers --------------------------------------------


def _find_resource(page, name: str):
	if not name:
		return None
	return next((r for r in page.resources if r.resource_name == name), None)


def _reload(ctx) -> None:
	ctx.emit("reload", resources=True)


def _describe_resource(r) -> dict:
	out = {"name": r.resource_name, "type": r.resource_type}
	for field in ("document_type", "document_name", "fields", "filters", "limit", "sort_field", "url"):
		if value := r.get(field):
			out[field] = value
	# Surface the lifecycle hooks (their full source, so the model can extend rather than clobber)
	# and whether auto-fetch is on, so update_data_source has the current state to work from.
	for field in ("transform", "on_success", "on_error"):
		if value := r.get(field):
			out[field] = value
	out["auto"] = bool(r.get("auto"))
	return out


# --- tool definitions -----------------------------------------------------

# The three JS lifecycle hooks. Each is a Code field whose source must DECLARE a function
# with an exact name (Studio invokes it by that name); shared by add + update so the
# contract can't drift. transform reshapes the result; on_success/on_error react to a fetch.
_TRANSFORM_PARAM = {
	"type": "string",
	"description": (
		"JavaScript that reshapes the fetched result before it becomes {{ <name>.data }}. MUST declare a "
		"function named exactly `transform` taking the raw result — the records array (Document List / "
		"API) or the doc (Document) — and RETURNING the new value. e.g. 'function transform(data) { return "
		'data.map(d => ({ ...d, label: d.first_name + " " + d.last_name })) }\'.'
	),
}
_ON_SUCCESS_PARAM = {
	"type": "string",
	"description": (
		"JavaScript run after a successful fetch. MUST declare a function named exactly `onSuccess` taking "
		"(data). The page context is in scope — variables are refs (write via .value), plus the other "
		"resources and route/router. e.g. 'function onSuccess(data) { rowCount.value = data.length }'."
	),
}
_ON_ERROR_PARAM = {
	"type": "string",
	"description": (
		"JavaScript run when the fetch fails. MUST declare a function named exactly `onError` taking "
		"(error). Same page context in scope. e.g. 'function onError(error) { loadFailed.value = true }'."
	),
}
_AUTO_PARAM = {
	"type": "boolean",
	"description": "Fetch automatically on page load (default true). Set false for on-demand sources.",
}

add_data_source = Tool(
	name="add_data_source",
	side="server",
	handler=run_add_data_source,
	description=(
		"Create a data source on the page so real Frappe records can render. Pick the type:\n"
		"• 'Document List' — many records of a DocType (a table/list). Needs document_type and "
		"fields[]; optional filters, limit, sort_field, sort_order.\n"
		"• 'Document' — one record. Needs document_type plus either document_name or "
		"fetch_document_using_filters + filters.\n"
		"• 'API Resource' — a REST endpoint. Needs url; optional method, params.\n"
		"Any type also accepts optional lifecycle hooks: transform (reshape the result), on_success / "
		"on_error (react to a fetch), and auto (fetch on load, default true).\n"
		"First confirm the DocType and field names with list_doctypes / get_doctype_fields. After "
		"this, the data is available as {{ <data_source_name>.data }} — bind blocks to it with "
		"set_repeater_data or bind_prop. Add the data source BEFORE laying out the blocks."
	),
	parameters={
		"type": "object",
		"properties": {
			"data_source_name": {
				"type": "string",
				"description": "A short identifier used in bindings, e.g. 'todos' → {{ todos.data }}.",
			},
			"data_source_type": {
				"type": "string",
				"enum": list(RESOURCE_TYPES),
				"description": "Document List | Document | API Resource.",
			},
			"document_type": {"type": "string", "description": "DocType to read (Document / Document List)."},
			"fields": {
				"type": "array",
				"items": {"type": "string"},
				"description": "Document List: fieldnames to fetch, e.g. ['name','description','status'].",
			},
			"filters": {
				"type": "object",
				"description": 'Filters as a map, e.g. {"status":"Open"} or {"status":["!=","Closed"]}.',
			},
			"limit": {"type": "integer", "description": "Document List: max rows to fetch."},
			"sort_field": {"type": "string", "description": "Document List: field to sort by."},
			"sort_order": {"type": "string", "enum": ["ASC", "DESC"], "description": "Sort direction."},
			"document_name": {"type": "string", "description": "Document: the record name to fetch."},
			"fetch_document_using_filters": {
				"type": "boolean",
				"description": "Document: resolve the record from filters instead of a fixed name.",
			},
			"url": {"type": "string", "description": "API Resource: the endpoint URL."},
			"method": {
				"type": "string",
				"enum": ["GET", "POST", "PUT", "DELETE"],
				"description": "API Resource: HTTP method (default GET).",
			},
			"params": {"type": "object", "description": "API Resource: request parameters map."},
			"auto": _AUTO_PARAM,
			"transform": _TRANSFORM_PARAM,
			"on_success": _ON_SUCCESS_PARAM,
			"on_error": _ON_ERROR_PARAM,
		},
		"required": ["data_source_name", "data_source_type"],
	},
)

list_data_sources = Tool(
	name="list_data_sources",
	side="server",
	handler=run_list_data_sources,
	description=(
		"List the page's existing data sources with their configuration (name, type, doctype, "
		"fields, filters, limit, sort). Use before update_data_source / delete_data_source, or to "
		"reuse a source that already exists."
	),
	parameters={"type": "object", "properties": {}},
)

update_data_source = Tool(
	name="update_data_source",
	side="server",
	handler=run_update_data_source,
	description=(
		"Change an existing data source's configuration. Identify it by data_source_name and pass "
		"only the fields you want to change (same fields as add_data_source). The type is fixed; "
		"create a new source to change the type."
	),
	parameters={
		"type": "object",
		"properties": {
			"data_source_name": {"type": "string", "description": "The data source to update."},
			"document_type": {"type": "string"},
			"fields": {"type": "array", "items": {"type": "string"}},
			"filters": {"type": "object"},
			"limit": {"type": "integer"},
			"sort_field": {"type": "string"},
			"sort_order": {"type": "string", "enum": ["ASC", "DESC"]},
			"document_name": {"type": "string"},
			"fetch_document_using_filters": {"type": "boolean"},
			"url": {"type": "string"},
			"method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
			"params": {"type": "object"},
			"auto": _AUTO_PARAM,
			"transform": _TRANSFORM_PARAM,
			"on_success": _ON_SUCCESS_PARAM,
			"on_error": _ON_ERROR_PARAM,
		},
		"required": ["data_source_name"],
	},
)

delete_data_source = Tool(
	name="delete_data_source",
	side="server",
	handler=run_delete_data_source,
	description=(
		"Remove a data source from the page by name. Warns if any block still binds it, so you can "
		"rebind or remove those blocks in the same turn."
	),
	parameters={
		"type": "object",
		"properties": {
			"data_source_name": {"type": "string", "description": "The data source to delete."},
		},
		"required": ["data_source_name"],
	},
)

TOOLS = [add_data_source, list_data_sources, update_data_source, delete_data_source]
