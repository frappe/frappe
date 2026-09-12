# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The document tools: `get_documents` reads, `write_document` changes.

Both mirror the API v2 handlers in `frappe.api.v2`, so an MCP client and a REST
client see the same semantics, the same permission checks and the same hooks.
"""

from typing import Any

import frappe
import frappe.client
from frappe.api import v2
from frappe.mcp.tools import Tool, form_dict

GET_DESCRIPTION = """Read documents from this Frappe site.

Give 'name' to read one whole document. Otherwise this lists documents, and you
can narrow the list with 'filters', 'fields', 'order_by', 'start' and 'limit'.
Set 'count_only' to count instead of listing.

'filters' takes a dict of equalities, such as {"status": "Open"}, or a list for
other operators, such as [["status", "in", ["Open", "Closed"]]].

The result reports 'has_next_page'. Page through with 'start' and 'limit'.
Call discover first if you do not know the DocType or its fields."""

GET_INPUT_SCHEMA = {
	"type": "object",
	"properties": {
		"doctype": {"type": "string", "description": "A DocType name, such as 'ToDo'."},
		"name": {"type": "string", "description": "Read this one document, whole."},
		"filters": {
			"type": ["object", "array"],
			"description": 'A dict of equalities, or a list such as [["status", "in", ["Open"]]].',
		},
		"fields": {
			"type": "array",
			"items": {"type": "string"},
			"description": "Fields to return. Defaults to the name only.",
		},
		"order_by": {"type": "string", "description": "For example 'creation desc'."},
		"start": {"type": "integer", "description": "Offset for paging. Defaults to 0."},
		"limit": {"type": "integer", "description": "Page size. Defaults to 20."},
		"count_only": {"type": "boolean", "description": "Count the matches instead of listing them."},
	},
	"required": ["doctype"],
	"additionalProperties": False,
}

DEFAULT_LIMIT = 20


def get_documents(arguments: dict[str, Any]) -> dict[str, Any]:
	doctype = _required(arguments, "doctype")
	name = arguments.get("name")

	if name:
		return {"document": v2.read_doc(doctype, name)}

	filters = arguments.get("filters")

	if arguments.get("count_only"):
		with form_dict({"filters": filters}):
			return {"doctype": doctype, "count": v2.count(doctype)}

	start = arguments.get("start") or 0
	limit = arguments.get("limit") or DEFAULT_LIMIT

	list_arguments = {
		"filters": filters,
		"fields": arguments.get("fields"),
		"order_by": arguments.get("order_by"),
		"start": start,
		"limit": limit,
	}

	with form_dict({key: value for key, value in list_arguments.items() if value is not None}):
		documents = v2.document_list(doctype)

	return {
		"doctype": doctype,
		"documents": documents,
		"start": start,
		"limit": limit,
		# `document_list` reports this on the response, which MCP does not use.
		"has_next_page": bool(frappe.response.pop("has_next_page", False)),
	}


WRITE_DESCRIPTION = """Create, update or delete one document on this Frappe site.

- create: give 'doctype' and 'data'.
- update: give 'doctype', 'name' and the 'data' to change.
- delete: give 'doctype' and 'name'.

Document lifecycle actions are not write actions. Submit, cancel and amend are
DocType methods, so run them through call_method.

Call discover first to learn which fields a DocType has and which are required."""

WRITE_INPUT_SCHEMA = {
	"type": "object",
	"properties": {
		"action": {"type": "string", "enum": ["create", "update", "delete"]},
		"doctype": {"type": "string", "description": "A DocType name, such as 'ToDo'."},
		"name": {"type": "string", "description": "The document to update or delete."},
		"data": {
			"type": "object",
			"description": "Field values. For create, everything the DocType requires.",
		},
	},
	"required": ["action", "doctype"],
	"additionalProperties": False,
}


def write_document(arguments: dict[str, Any]) -> dict[str, Any]:
	action = _required(arguments, "action")
	doctype = _required(arguments, "doctype")
	data = arguments.get("data") or {}

	if action == "create":
		with form_dict(data):
			return {"action": action, "document": v2.create_doc(doctype)}

	name = _required(arguments, "name")

	if action == "update":
		with form_dict(data):
			return {"action": action, "document": v2.update_doc(doctype, name)}

	if action == "delete":
		frappe.client.delete_doc(doctype, name)
		return {"action": action, "doctype": doctype, "name": name}

	frappe.throw(f"Unknown action {action}. Use create, update or delete.", frappe.ValidationError)


def _required(arguments: dict[str, Any], key: str) -> Any:
	value = arguments.get(key)
	if not value:
		frappe.throw(f"'{key}' is required", frappe.ValidationError)
	return value


GET_DOCUMENTS = Tool(
	name="get_documents",
	title="Read documents",
	description=GET_DESCRIPTION,
	input_schema=GET_INPUT_SCHEMA,
	annotations={"readOnlyHint": True},
	handler=get_documents,
)

WRITE_DOCUMENT = Tool(
	name="write_document",
	title="Create, update or delete a document",
	description=WRITE_DESCRIPTION,
	input_schema=WRITE_INPUT_SCHEMA,
	annotations={"destructiveHint": True, "idempotentHint": False},
	handler=write_document,
)
