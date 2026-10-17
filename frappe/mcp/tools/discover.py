# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Discover site metadata through Frappe's existing API discovery handlers."""

from typing import TYPE_CHECKING

from pydantic import Field

import frappe
from frappe.api import discovery
from frappe.mcp.tools import Tool, ToolArguments
from frappe.model import NO_VALUE_FIELDS

if TYPE_CHECKING:
	from frappe.core.doctype.docfield.docfield import DocField

LAYOUT_FIELDTYPES = NO_VALUE_FIELDS - {"Table", "Table MultiSelect"}
PERMISSION_TYPES = ("read", "write", "create", "delete", "submit", "cancel", "amend")
SEARCH_LIMIT = 50


class SearchDoctypesArguments(ToolArguments):
	query: str | None = Field(default=None, min_length=1)
	module: str | None = Field(default=None, min_length=1)


class DoctypeArguments(ToolArguments):
	doctype: str = Field(min_length=1)


class SearchMethodsArguments(ToolArguments):
	query: str = Field(min_length=1)


class MethodSchemaArguments(ToolArguments):
	method: str = Field(min_length=1)
	doctype: str | None = Field(default=None, min_length=1)


def search_doctypes(query: str | None = None, module: str | None = None) -> list[dict]:
	filters = {"istable": 0}
	if query is not None:
		filters["name"] = ("like", f"%{query}%")
	if module is not None:
		filters["module"] = module
	return frappe.get_all(
		"DocType",
		filters=filters,
		fields=["name", "module", "issingle", "is_submittable"],
		order_by="name",
		limit=SEARCH_LIMIT,
	)


def search_methods(query: str) -> list[dict]:
	return [without(entry, "type") for entry in discovery.search(query)["results"]]


def method_schema(method: str, doctype: str | None = None) -> dict:
	if doctype is not None:
		return without(discovery.doctype_method(doctype, method), "type", "kind", "doctype", "method")
	return without(discovery.method(method), "type", "kind")


def document_methods(doctype: str) -> list[dict]:
	return [
		without(entry, "type", "kind", "doctype") for entry in discovery.doctype_methods(doctype)["methods"]
	]


def doctype_schema(doctype: str) -> dict:
	meta = frappe.get_meta(doctype)
	result = {
		"module": meta.module,
		"is_submittable": bool(meta.is_submittable),
		"is_single": bool(meta.issingle),
		"is_child_table": bool(meta.istable),
		"title_field": meta.title_field,
		"fields": [field_schema(field) for field in meta.fields if field.fieldtype not in LAYOUT_FIELDTYPES],
		"permissions": {
			# The return value is exposed as metadata, not used to authorize an operation.
			# nosemgrep: frappe-semgrep-rules.rules.unchecked-frappe-permission-call
			permission: False if meta.istable else frappe.has_permission(doctype, permission)
			for permission in PERMISSION_TYPES
		},
	}
	return result


def field_schema(field: "DocField") -> dict:
	result = {
		"fieldname": field.fieldname,
		"fieldtype": field.fieldtype,
		"label": field.label,
		"options": field.options,
		"reqd": bool(field.reqd),
		"read_only": bool(field.read_only),
		"permlevel": field.permlevel or 0,
	}
	return {key: value for key, value in result.items() if value is not None}


def without(data: dict, *keys: str) -> dict:
	return {key: value for key, value in data.items() if key not in keys}


SEARCH_DOCTYPES = Tool(
	name="search_doctypes",
	description="Search DocTypes by name or module. Returns up to 50, without child tables.",
	arguments=SearchDoctypesArguments,
	handler=search_doctypes,
	annotations={"readOnlyHint": True},
)

GET_DOCTYPE_SCHEMA = Tool(
	name="get_doctype_schema",
	description="Get fields and permissions of a DocType.",
	arguments=DoctypeArguments,
	handler=doctype_schema,
	annotations={"readOnlyHint": True},
)

SEARCH_METHODS = Tool(
	name="search_methods",
	description="Search whitelisted methods and document methods.",
	arguments=SearchMethodsArguments,
	handler=search_methods,
	annotations={"readOnlyHint": True},
)

GET_METHOD_SCHEMA = Tool(
	name="get_method_schema",
	description=(
		"Get arguments and docstring of a whitelisted method by dotted path, or by method name with doctype."
	),
	arguments=MethodSchemaArguments,
	handler=method_schema,
	annotations={"readOnlyHint": True},
)

LIST_DOCUMENT_METHODS = Tool(
	name="list_document_methods",
	description="List whitelisted document methods of a DocType.",
	arguments=DoctypeArguments,
	handler=document_methods,
	annotations={"readOnlyHint": True},
)
