# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Discover site metadata through Frappe's existing API discovery handlers."""

from typing import TYPE_CHECKING, Self

from pydantic import Field, model_validator

import frappe
from frappe import _
from frappe.api import discovery
from frappe.mcp.tools import Tool, ToolArguments
from frappe.model import NO_VALUE_FIELDS

if TYPE_CHECKING:
	from frappe.core.doctype.docfield.docfield import DocField

LAYOUT_FIELDTYPES = NO_VALUE_FIELDS - {"Table", "Table MultiSelect"}
PERMISSION_TYPES = ("read", "write", "create", "delete", "submit", "cancel", "amend")
SEARCH_LIMIT = 50


class DiscoverArguments(ToolArguments):
	query: str | None = Field(default=None, min_length=1, description="Search DocType names and API methods.")
	doctype: str | None = Field(default=None, min_length=1, description="DocType whose schema to inspect.")
	method: str | None = Field(
		default=None,
		min_length=1,
		description="RPC method path, or controller method name when doctype is provided.",
	)

	@model_validator(mode="after")
	def check_subject(self) -> Self:
		if self.query is not None and (self.doctype is not None or self.method is not None):
			raise ValueError(_("Use query alone, or select a DocType or method"))
		return self


def handle(query: str | None = None, doctype: str | None = None, method: str | None = None) -> dict:
	if doctype and method:
		return discovery.doctype_method(doctype, method)
	if doctype:
		return doctype_schema(doctype)
	if method:
		return discovery.method(method)
	if query:
		return search(query)
	return site_summary()


def site_summary() -> dict:
	doctypes = frappe.get_all("DocType", fields=["module"], filters={"istable": 0})
	modules = sorted({row.module for row in doctypes if row.module})
	return {
		"type": "site",
		"site": frappe.local.site,
		"user": frappe.session.user,
		"roles": sorted(frappe.get_roles()),
		"counts": {"doctypes": len(doctypes), "modules": len(modules)},
		"modules": modules,
		"next": _("Use query to search, or doctype to inspect a schema."),
	}


def search(query: str) -> dict:
	result = {
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
		result["methods_unavailable"] = _("Method discovery needs the System Manager role.")
	except discovery.DiscoveryCacheUnavailable as error:
		# DocType results remain useful while the existing API index is being built.
		result["methods_unavailable"] = str(error)
	return result


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
			permission: False if meta.istable else frappe.has_permission(doctype, permission)
			for permission in PERMISSION_TYPES
		},
	}
	if meta.istable:
		# Child rows have no independent permissions or document methods.
		result["methods"] = []
	else:
		try:
			result["methods"] = discovery.doctype_methods(doctype)["methods"]
		except frappe.PermissionError:
			result["methods_unavailable"] = _("Method discovery needs the System Manager role.")
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


TOOL = Tool(
	name="discover",
	description=(
		"Inspect this site's metadata before choosing DocType names, fields or methods. "
		"No arguments returns the site summary; query searches; doctype returns a schema; "
		"method returns an RPC contract; doctype with method returns a controller method contract. "
		"Schema discovery is broad, but document access remains permission-controlled. "
		"Permission flags describe DocType access, not access to every document or field. "
		"Child rows use their parent's permissions. Method discovery requires System Manager."
	),
	arguments=DiscoverArguments,
	handler=handle,
	annotations={"readOnlyHint": True},
)
