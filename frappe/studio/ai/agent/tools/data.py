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

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import dangling_binding_warning, load_page, save_page, text_arg
from studio.ai.block_codec import BlockCodec
from studio.ai.prompt_fragments import FILTER_FORMAT_RULE, ON_ERROR_RULE, ON_SUCCESS_RULE, TRANSFORM_RULE

RESOURCE_TYPES = ("Document List", "Document", "API Resource")

# Operators Frappe's query engine accepts as the first element of a [operator, value]
# filter. A list whose first element isn't one of these is a bare value-list the model
# meant as "in" — it would crash every fetch with KeyError at runtime, so refuse it here.
FILTER_OPERATORS = {
	"=", "!=", "<", ">", "<=", ">=",
	"like", "not like", "in", "not in", "is", "is not", "not is",
	"between", "timespan", "previous", "next",
	"descendants of", "not descendants of", "ancestors of", "not ancestors of",
}  # fmt: skip


MULTI_VALUE_OPERATORS = {"in", "not in"}


def invalid_filter_message(filters) -> str | None:
	"""Reject filter shapes that would crash at fetch time (Frappe unpacks a list
	filter as exactly `operator, value = value`), repairing the one unambiguous slip
	IN PLACE: a flat ["in", "A", "B"] can only mean ["in", ["A", "B"]]."""
	if not isinstance(filters, dict):
		return None
	for field, value in filters.items():
		if not isinstance(value, list | tuple):
			continue
		operator = str(value[0]).casefold() if value else ""
		if operator not in FILTER_OPERATORS:
			return (
				f"FAILED: filter for '{field}' is a bare list {list(value)} — Frappe reads a list as "
				f"[operator, value], so this crashes at fetch time. For multiple values use "
				f'{{"{field}": ["in", {list(value)}]}}; for one value pass it directly or with an '
				f'explicit operator like ["!=", "Closed"].'
			)
		if len(value) > 2:
			if operator in MULTI_VALUE_OPERATORS:
				filters[field] = [value[0], list(value[1:])]
				continue
			return (
				f"FAILED: filter for '{field}' has {len(value)} elements {list(value)} — a list filter "
				f'is exactly [operator, value]. Pass ["{value[0]}", <one value>], or use "in"/"not in" '
				f'with a nested list: ["in", ["A", "B"]].'
			)
	return None


def run_add_data_source(ctx, args: dict) -> str:
	name = text_arg(args.get("data_source_name"))
	source_type = text_arg(args.get("data_source_type"))
	if not name:
		return "FAILED: data_source_name is required."
	if source_type not in RESOURCE_TYPES:
		return f"FAILED: data_source_type must be one of {list(RESOURCE_TYPES)}."

	if error := invalid_filter_message(args.get("filters")):
		return error

	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if _find_resource(page, name):
		return f"FAILED: a data source named '{name}' already exists. Use update_data_source to change it."

	page.append("resources", _build_row(name, source_type, args))
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx, page)
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
	if error := invalid_filter_message(args.get("filters")):
		return error
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	row = _find_resource(page, name)
	if row is None:
		return f"FAILED: no data source named '{name}'. Call list_data_sources to see the current set."

	changed = _apply_changes(row, args)
	if not changed:
		return "Nothing to update — pass the fields you want to change."
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx, page)
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
	_reload(ctx, page)

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
			row[field] = args[field]
	return row


def _apply_changes(row, args: dict) -> list[str]:
	"""Mutate an existing child row in place with the provided fields. Returns the
	list of fields that changed (for the result message)."""
	changed = []
	for field in _RESOURCE_FIELDS:
		if args.get(field) is not None:
			setattr(row, field, args[field])
			changed.append(field)
	return changed


# --- resource-specific helpers --------------------------------------------


def _find_resource(page, name: str):
	if not name:
		return None
	return next((r for r in page.resources if r.resource_name == name), None)


def _reload(ctx, page) -> None:
	# Ship the saved page's modified so the editor re-syncs its optimistic-lock timestamp without an extra fetch
	ctx.emit("reload", resources=True, modified=page.modified)


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

# The three JS lifecycle hooks and the filter format live in prompt_fragments so the same rule
# the agent reads in the data-wiring prompt is the one it reads here at the call site. Shared by
# add + update so the two can't drift.
_TRANSFORM_PARAM = {"type": "string", "description": TRANSFORM_RULE}
_ON_SUCCESS_PARAM = {"type": "string", "description": ON_SUCCESS_RULE}
_ON_ERROR_PARAM = {"type": "string", "description": ON_ERROR_RULE}
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
				"description": FILTER_FORMAT_RULE,
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
			"filters": {"type": "object", "description": FILTER_FORMAT_RULE},
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
