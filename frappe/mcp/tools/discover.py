# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The `discover` tool: one lookup tool, the arguments select the subject."""

from typing import Any

import frappe
from frappe.api import discovery
from frappe.mcp.tools import Tool

DESCRIPTION = """Look up what this Frappe site holds. Use it before you guess a DocType name, a field name or a method path.

The arguments select the subject:
- no arguments: a site summary with the modules present.
- query: search DocType names and whitelisted methods.
- doctype: the fields, permissions and methods of one DocType.
- doctype and method: the contract of one DocType method.
- method: the contract of one RPC method.

Method discovery needs the System Manager role. Without it you still get the DocType schema."""

INPUT_SCHEMA = {
	"type": "object",
	"properties": {
		"query": {
			"type": "string",
			"description": "Free text. Matches DocType names and whitelisted methods.",
		},
		"doctype": {"type": "string", "description": "A DocType name, such as 'Sales Invoice'."},
		"method": {
			"type": "string",
			"description": (
				"A dotted RPC path, such as 'frappe.client.get_count'. "
				"With 'doctype', a controller method name instead, such as 'submit'."
			),
		},
	},
	"additionalProperties": False,
}

# Fields that only shape the form. They carry no data and waste the model's context.
LAYOUT_FIELDTYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Heading",
	"Image",
	"Fold",
}

PERMISSION_TYPES = ("read", "write", "create", "delete", "submit", "cancel", "amend")

METHODS_UNAVAILABLE = "Method discovery needs the System Manager role."

SEARCH_LIMIT = 50


def handle(arguments: dict[str, Any]) -> dict[str, Any]:
	doctype = arguments.get("doctype")
	method = arguments.get("method")
	query = arguments.get("query")

	if doctype and method:
		return discovery.doctype_method(doctype, method)
	if doctype:
		return _doctype_schema(doctype)
	if method:
		return discovery.method(method)
	if query:
		return _search(query)

	return _site_summary()


def _site_summary() -> dict[str, Any]:
	doctypes = frappe.get_all("DocType", fields=["module"], filters={"istable": 0})
	modules = sorted({row.module for row in doctypes if row.module})

	return {
		"type": "site",
		"site": frappe.local.site,
		"user": frappe.session.user,
		"roles": sorted(frappe.get_roles()),
		"counts": {"doctypes": len(doctypes), "modules": len(modules)},
		"modules": modules,
		"next": ("Call discover again with 'query' to search, or with 'doctype' to read a schema."),
	}


def _search(query: str) -> dict[str, Any]:
	result: dict[str, Any] = {
		"type": "search",
		"query": query,
		"doctypes": frappe.get_all(
			"DocType",
			filters={"name": ("like", f"%{query}%"), "istable": 0},
			fields=["name", "module", "issingle", "is_submittable"],
			order_by="name",
			limit=SEARCH_LIMIT,
		),
	}

	try:
		result["methods"] = discovery.search(query)["results"]
	except frappe.PermissionError:
		result["methods_unavailable"] = METHODS_UNAVAILABLE

	return result


def _doctype_schema(doctype: str) -> dict[str, Any]:
	"""A compact schema. Raw meta is large and most of it does not help an agent."""
	meta = frappe.get_meta(doctype)

	schema: dict[str, Any] = {
		"type": "doctype",
		"doctype": meta.name,
		"module": meta.module,
		"is_submittable": bool(meta.is_submittable),
		"is_single": bool(meta.issingle),
		"is_child_table": bool(meta.istable),
		"title_field": meta.title_field,
		"fields": [_field(df) for df in meta.fields if df.fieldtype not in LAYOUT_FIELDTYPES],
		"permissions": {
			permission: frappe.has_permission(doctype, permission) for permission in PERMISSION_TYPES
		},
	}

	try:
		schema["methods"] = discovery.doctype_methods(doctype)["methods"]
	except frappe.PermissionError:
		schema["methods_unavailable"] = METHODS_UNAVAILABLE

	return schema


def _field(df) -> dict[str, Any]:
	field = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": df.label,
		"options": df.options,
		"reqd": bool(df.reqd) or None,
		"read_only": bool(df.read_only) or None,
	}
	return {key: value for key, value in field.items() if value is not None}


TOOL = Tool(
	name="discover",
	title="Discover the site",
	description=DESCRIPTION,
	input_schema=INPUT_SCHEMA,
	annotations={"readOnlyHint": True},
	handler=handle,
)
