# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Discover site metadata through Frappe's existing API discovery handlers."""

from typing import TYPE_CHECKING

from pydantic import Field

import frappe
from frappe import _
from frappe.api import discovery
from frappe.mcp import protocol
from frappe.mcp.tools import Tool, ToolArguments
from frappe.model import NO_VALUE_FIELDS

if TYPE_CHECKING:
	from frappe.core.doctype.docfield.docfield import DocField

LAYOUT_FIELDTYPES = NO_VALUE_FIELDS - {"Table", "Table MultiSelect"}
PERMISSION_TYPES = ("read", "write", "create", "delete", "submit", "cancel", "amend")
SEARCH_LIMIT = 50


class SiteInfoArguments(ToolArguments):
	pass


class SearchDoctypesArguments(ToolArguments):
	query: str | None = Field(default=None, min_length=1, description="Search DocType names.")
	module: str | None = Field(default=None, min_length=1, description="Filter by module.")


class DoctypeArguments(ToolArguments):
	doctype: str = Field(min_length=1, description="DocType to inspect.")


class SearchMethodsArguments(ToolArguments):
	query: str = Field(min_length=1, description="Search whitelisted methods by keyword or path.")


class MethodSchemaArguments(ToolArguments):
	method: str = Field(min_length=1, description="Full dotted path or API Server Script name.")


class DocumentMethodSchemaArguments(DoctypeArguments):
	method: str = Field(min_length=1, description="Whitelisted document instance method name.")


def site_summary() -> dict:
	doctypes = frappe.get_all("DocType", fields=["module"], filters={"istable": 0})
	modules = sorted({row.module for row in doctypes if row.module})
	return {
		"type": "site",
		"server_info": protocol.server_info(),
		"instructions": protocol.server_instructions(),
		"site": frappe.local.site,
		"user": frappe.session.user,
		"roles": sorted(frappe.get_roles()),
		"counts": {"doctypes": len(doctypes), "modules": len(modules)},
		"modules": modules,
		"next": _("Use search_doctypes to find DocTypes, then get_doctype_schema to inspect fields."),
	}


def search_doctypes(query: str | None = None, module: str | None = None) -> dict:
	filters = {"istable": 0}
	if query is not None:
		filters["name"] = ("like", f"%{query}%")
	if module is not None:
		filters["module"] = module
	return {
		"type": "search",
		"query": query,
		"doctypes": frappe.get_all(
			"DocType",
			filters=filters,
			fields=["name", "module", "issingle", "is_submittable"],
			order_by="name",
			limit=SEARCH_LIMIT,
		),
	}


def search_methods(query: str) -> dict:
	return discovery.search(query)


def doctype_schema(doctype: str) -> dict:
	meta = frappe.get_meta(doctype)
	result = {
		"type": "doctype",
		"doctype": meta.name,
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


GET_SITE_INFO = Tool(
	name="get_site_info",
	description="Identify the connected site, authenticated user, roles and available modules.",
	arguments=SiteInfoArguments,
	handler=site_summary,
	annotations={"readOnlyHint": True},
)

SEARCH_DOCTYPES = Tool(
	name="search_doctypes",
	description="Find DocTypes by name or module. Returns up to 50 names in alphabetical order, excluding child tables.",
	arguments=SearchDoctypesArguments,
	handler=search_doctypes,
	annotations={"readOnlyHint": True},
)

GET_DOCTYPE_SCHEMA = Tool(
	name="get_doctype_schema",
	description=(
		"Inspect DocType fields and permissions before reading or writing. Schema discovery is broad. "
		"Permission flags do not guarantee access to every document or field. Child rows use parent permissions. "
		"Use list_document_methods separately to discover instance methods."
	),
	arguments=DoctypeArguments,
	handler=doctype_schema,
	annotations={"readOnlyHint": True},
)

SEARCH_METHODS = Tool(
	name="search_methods",
	description="Find whitelisted API functions and document methods by keyword or path. Requires System Manager.",
	arguments=SearchMethodsArguments,
	handler=search_methods,
	annotations={"readOnlyHint": True},
)

GET_METHOD_SCHEMA = Tool(
	name="get_method_schema",
	description="Inspect a whitelisted API function's arguments and documentation. Requires System Manager.",
	arguments=MethodSchemaArguments,
	handler=discovery.method,
	annotations={"readOnlyHint": True},
)

LIST_DOCUMENT_METHODS = Tool(
	name="list_document_methods",
	description="List whitelisted instance methods for a DocType. Requires System Manager.",
	arguments=DoctypeArguments,
	handler=discovery.doctype_methods,
	annotations={"readOnlyHint": True},
)

GET_DOCUMENT_METHOD_SCHEMA = Tool(
	name="get_document_method_schema",
	description="Inspect a whitelisted document instance method's arguments and documentation. Requires System Manager.",
	arguments=DocumentMethodSchemaArguments,
	handler=discovery.doctype_method,
	annotations={"readOnlyHint": True},
)
