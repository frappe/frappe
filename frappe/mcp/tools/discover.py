# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Discover site metadata through Frappe's existing API discovery handlers."""

from typing import TYPE_CHECKING, Annotated

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


SearchText = Annotated[str, Field(min_length=1)]


class SearchDoctypesArguments(ToolArguments):
	query: SearchText | Annotated[list[SearchText], Field(min_length=1)] | None = None
	limit: int = Field(default=SEARCH_LIMIT, ge=1)


class GetDoctypeSchemaArguments(ToolArguments):
	doctype: str = Field(min_length=1)


class SearchMethodsArguments(ToolArguments):
	query: str = Field(min_length=1)


class GetMethodSchemaArguments(ToolArguments):
	method: str = Field(min_length=1)
	doctype: str | None = Field(default=None, min_length=1)


class ListDocumentMethodsArguments(ToolArguments):
	doctype: str = Field(min_length=1)


def search_doctypes(query: str | list[str] | None = None, limit: int = SEARCH_LIMIT) -> list[str]:
	if isinstance(query, str):
		query = [query]
	return frappe.get_all(
		"DocType",
		filters={"istable": 0},
		or_filters=[("name", "like", f"%{text}%") for text in query or ()],
		pluck="name",
		order_by="name",
		limit=limit,
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
	description=(
		"Search DocType names that contain the query string, or any of a list of them. "
		"Returns up to limit names (default 50), without child tables."
	),
	arguments=SearchDoctypesArguments,
	handler=search_doctypes,
	annotations={"readOnlyHint": True},
)

GET_DOCTYPE_SCHEMA = Tool(
	name="get_doctype_schema",
	description="Get fields and permissions of a DocType.",
	arguments=GetDoctypeSchemaArguments,
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
	arguments=GetMethodSchemaArguments,
	handler=method_schema,
	annotations={"readOnlyHint": True},
)

LIST_DOCUMENT_METHODS = Tool(
	name="list_document_methods",
	description="List whitelisted document methods of a DocType.",
	arguments=ListDocumentMethodsArguments,
	handler=document_methods,
	annotations={"readOnlyHint": True},
)
