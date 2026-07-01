"""Variable tools — full CRUD over a page's reactive variables.

A variable is a `Studio Page Variable` child row (backing table: `variables`) — a
piece of reactive page state (a counter, a toggle, a filter value). Like the data
tools these are server-side: the handler mutates the `Studio Page` doc, saves, and
emits a `reload` event so the canvas re-reads variables and `{{ <name> }}` bindings
resolve. Bind a block to a variable with the client tool `bind_prop`.

`initial_value` is stored the way the frontend decodes it per type (see
studio/frontend/src/utils/helpers.ts `getInitialVariableValue`): Number as a bare
number, Boolean as 'true'/'false', and Object AND String as JSON — so a String's
stored value is JSON-encoded (`"hi"`, with quotes). `_encode_initial_value` handles
that, so the model just passes a plain value.
"""

import json
import re

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import dangling_binding_warning, load_page, save_page, text_arg
from studio.ai.block_codec import BlockCodec

VARIABLE_TYPES = ("String", "Number", "Boolean", "Object")
# A binding name has to be a bare JS identifier — it's spread into the eval context
# and referenced as {{ <name> }}.
_NAME_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def run_add_variable(ctx, args: dict) -> str:
	name = text_arg(args.get("variable_name"))
	var_type = text_arg(args.get("variable_type")) or "String"
	if error := _validate_name(name):
		return f"FAILED: {error}"
	if var_type not in VARIABLE_TYPES:
		return f"FAILED: variable_type must be one of {list(VARIABLE_TYPES)}."

	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if _find_variable(page, name):
		return f"FAILED: a variable named '{name}' already exists. Use update_variable to change it."

	page.append(
		"variables",
		{
			"variable_name": name,
			"variable_type": var_type,
			"initial_value": _encode_initial_value(var_type, args.get("initial_value")),
		},
	)
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)
	return f"Added {var_type} variable '{name}'. Bind blocks to it with {{{{ {name} }}}}."


def run_list_variables(ctx, args: dict) -> str:
	page = load_page(ctx)
	if page is None:
		return "No page in context."
	if not page.variables:
		return "No variables defined on this page yet."
	out = [
		{"name": v.variable_name, "type": v.variable_type, "initial_value": v.initial_value}
		for v in page.variables
	]
	return f"{len(out)} variable(s):\n" + BlockCodec.to_json(out)


def run_update_variable(ctx, args: dict) -> str:
	name = text_arg(args.get("variable_name"))
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	row = _find_variable(page, name)
	if row is None:
		return f"FAILED: no variable named '{name}'. Call list_variables to see the current set."

	changed = []
	if var_type := text_arg(args.get("variable_type")):
		if var_type not in VARIABLE_TYPES:
			return f"FAILED: variable_type must be one of {list(VARIABLE_TYPES)}."
		row.variable_type = var_type
		changed.append("variable_type")
	if args.get("initial_value") is not None:
		row.initial_value = _encode_initial_value(row.variable_type, args["initial_value"])
		changed.append("initial_value")
	if not changed:
		return "Nothing to update — pass variable_type and/or initial_value."

	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)
	return f"Updated variable '{name}' ({', '.join(changed)})."


def run_delete_variable(ctx, args: dict) -> str:
	name = text_arg(args.get("variable_name"))
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	row = _find_variable(page, name)
	if row is None:
		return f"FAILED: no variable named '{name}'."

	page.variables.remove(row)
	if error := save_page(page):
		return f"FAILED: {error}"
	_reload(ctx)

	warning = dangling_binding_warning(ctx, name)
	return f"Deleted variable '{name}'." + (f" {warning}" if warning else "")


# --- helpers --------------------------------------------------------------


def _validate_name(name: str) -> str | None:
	if not name:
		return "variable_name is required."
	if not _NAME_RE.match(name):
		return f"'{name}' is not a valid variable name — use letters, digits and underscores, starting with a letter."
	return None


def _find_variable(page, name: str):
	if not name:
		return None
	return next((v for v in page.variables if v.variable_name == name), None)


def _encode_initial_value(variable_type: str, value) -> str:
	"""Encode `value` into the stored string the frontend decodes for this type.
	Number → bare number; Boolean → 'true'/'false'; Object/String → JSON."""
	if variable_type == "Number":
		try:
			num = float(value)
			return str(int(num)) if num == int(num) else str(num)
		except (TypeError, ValueError):
			return "0"
	if variable_type == "Boolean":
		truthy = value if isinstance(value, bool) else str(value).strip().lower() in ("true", "1", "yes")
		return "true" if truthy else "false"
	if variable_type == "Object":
		if isinstance(value, dict | list):
			return frappe.as_json(value, indent=None)
		try:
			json.loads(value)  # already a JSON string
			return value
		except (TypeError, ValueError):
			return "{}"
	# String — the frontend JSON.parses it, so store a JSON-encoded string.
	if value is None:
		return '""'
	return frappe.as_json(value if isinstance(value, str) else str(value))


def _reload(ctx) -> None:
	ctx.emit("reload", variables=True)


# --- tool definitions -----------------------------------------------------

add_variable = Tool(
	name="add_variable",
	side="server",
	handler=run_add_variable,
	description=(
		"Create a reactive page variable — client-side state like a counter, a toggle, or a "
		"selected filter. Once created it's available in bindings as {{ <variable_name> }}. Show or "
		"use it by binding a block prop with bind_prop (e.g. a TextBlock's 'text' to the variable). "
		"Pass initial_value as a plain value for the type: 0 for a Number, true/false for a Boolean, "
		"the text for a String, or a JSON object/array for Object."
	),
	parameters={
		"type": "object",
		"properties": {
			"variable_name": {
				"type": "string",
				"description": "Identifier used in bindings, e.g. 'counter' → {{ counter }}. Letters/digits/underscore, must start with a letter.",
			},
			"variable_type": {
				"type": "string",
				"enum": list(VARIABLE_TYPES),
				"description": "String | Number | Boolean | Object. Defaults to String.",
			},
			"initial_value": {
				"type": "string",
				"description": "Starting value: e.g. '0' (Number), 'true' (Boolean), 'Hello' (String), '{\"open\":false}' (Object).",
			},
		},
		"required": ["variable_name", "variable_type"],
	},
)

list_variables = Tool(
	name="list_variables",
	side="server",
	handler=run_list_variables,
	description=(
		"List the page's variables with their type and initial value. Use before "
		"update_variable / delete_variable, or to reuse a variable that already exists."
	),
	parameters={"type": "object", "properties": {}},
)

update_variable = Tool(
	name="update_variable",
	side="server",
	handler=run_update_variable,
	description=(
		"Change an existing variable's type and/or initial value. Identify it by variable_name and "
		"pass only what you want to change."
	),
	parameters={
		"type": "object",
		"properties": {
			"variable_name": {"type": "string", "description": "The variable to update."},
			"variable_type": {"type": "string", "enum": list(VARIABLE_TYPES)},
			"initial_value": {"type": "string", "description": "New starting value (encoded for the type)."},
		},
		"required": ["variable_name"],
	},
)

delete_variable = Tool(
	name="delete_variable",
	side="server",
	handler=run_delete_variable,
	description=(
		"Remove a variable from the page by name. Warns if any block still binds it, so you can "
		"rebind or remove those blocks in the same turn."
	),
	parameters={
		"type": "object",
		"properties": {
			"variable_name": {"type": "string", "description": "The variable to delete."},
		},
		"required": ["variable_name"],
	},
)

TOOLS = [add_variable, list_variables, update_variable, delete_variable]
