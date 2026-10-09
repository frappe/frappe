# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Document tools reuse REST API v2 permissions and controller hooks."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

import frappe
from frappe import _
from frappe.api import v2
from frappe.mcp.tools import Tool, ToolArguments, form_dict


class GetDocumentsArguments(ToolArguments):
	doctype: str = Field(min_length=1, description="DocType to read.")
	name: str | None = Field(default=None, min_length=1, description="Read one complete document.")
	filters: dict[str, Any] | list[Any] | None = Field(
		default=None, description="Equality filters or Frappe operator filters."
	)
	fields: list[str] | None = Field(default=None, description="List fields; defaults to name only.")
	order_by: str | None = Field(default=None, description="List order, such as creation desc.")
	start: int = Field(default=0, ge=0, description="List offset.")
	limit: int = Field(default=20, ge=1, description="List page size.")
	count_only: bool = Field(default=False, description="Count permitted matches instead of listing.")

	@model_validator(mode="after")
	def check_mode(self) -> Self:
		if self.name is not None and self.count_only:
			raise ValueError(_("Use name to read one document, or count_only to count matches"))
		return self


class WriteDocumentArguments(ToolArguments):
	action: Literal["create", "update", "delete"]
	doctype: str = Field(min_length=1, description="DocType to change.")
	name: str | None = Field(default=None, min_length=1, description="Document to update or delete.")
	data: dict[str, Any] | None = Field(default=None, description="Field values for create or update.")

	@model_validator(mode="after")
	def check_action(self) -> Self:
		if self.action in ("update", "delete") and self.name is None:
			raise ValueError(_("name is required for update or delete"))
		if self.action in ("create", "update") and self.data is None:
			raise ValueError(_("data is required for create or update"))
		if self.action == "create" and self.name is not None:
			raise ValueError(_("For create, specify a document name inside data"))
		if self.action == "delete" and self.data is not None:
			raise ValueError(_("Delete accepts a document name, not data"))
		return self


def get_documents(
	doctype: str,
	name: str | None = None,
	filters: dict[str, Any] | list[Any] | None = None,
	fields: list[str] | None = None,
	order_by: str | None = None,
	start: int = 0,
	limit: int = 20,
	count_only: bool = False,
) -> dict:
	if name is not None:
		return {"document": v2.read_doc(doctype, name)}
	if count_only:
		with form_dict({"filters": filters}):
			return {"doctype": doctype, "count": v2.count(doctype)}

	arguments = {"filters": filters, "fields": fields, "order_by": order_by, "start": start, "limit": limit}
	with form_dict({key: value for key, value in arguments.items() if value is not None}):
		documents = v2.document_list(doctype)
		# The REST handler's pagination metadata belongs to its temporary response.
		has_next_page = bool(frappe.response.get("has_next_page"))
	return {
		"doctype": doctype,
		"documents": documents,
		"start": start,
		"limit": limit,
		"has_next_page": has_next_page,
	}


def write_document(
	action: Literal["create", "update", "delete"],
	doctype: str,
	name: str | None = None,
	data: dict[str, Any] | None = None,
) -> dict:
	with form_dict(data or {}):
		if action == "create":
			return {"action": action, "document": v2.create_doc(doctype)}
		if action == "update":
			return {"action": action, "document": v2.update_doc(doctype, name)}
		v2.delete_doc(doctype, name)
		return {"action": action, "doctype": doctype, "name": name}


GET_DOCUMENTS = Tool(
	name="get_documents",
	description=(
		"Read documents using your Frappe permissions. Supply name to read one complete document; "
		"otherwise list matches using filters, fields, order_by, start and limit. "
		"List fields default to name only, start to 0 and limit to 20. "
		"Use has_next_page to continue paging. Set count_only to count filtered matches; "
		"list field selection, ordering and pagination do not apply to counts or named reads. "
		'Filters accept an object or operator lists such as [["status", "in", ["Open"]]]. '
		"Use discover first to find DocTypes and fields."
	),
	arguments=GetDocumentsArguments,
	handler=get_documents,
	annotations={"readOnlyHint": True},
)


WRITE_DOCUMENT = Tool(
	name="write_document",
	description=(
		"Create, update or delete one document using your Frappe permissions. "
		"For create supply action, doctype and data; put a custom document name inside data. "
		"For update supply action, doctype, name and data. For delete supply action, doctype and name. "
		"Frappe validates document fields and runs the normal controller hooks. "
		"A failed operation rolls back its database changes and runs its rollback cleanup. "
		"Use discover to inspect fields and requirements before writing. "
		"Submit and cancel are lifecycle methods for call_method, not write actions."
	),
	arguments=WriteDocumentArguments,
	handler=write_document,
	annotations={"destructiveHint": True, "idempotentHint": False},
)
