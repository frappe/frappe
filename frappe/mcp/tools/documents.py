# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Document tools reuse REST API v2 permissions and controller hooks."""

from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.mcp.tools import Tool, ToolArguments, form_dict


class DoctypeArguments(ToolArguments):
	doctype: str = Field(min_length=1, description="DocType to read or change.")


class DocumentArguments(DoctypeArguments):
	name: str = Field(min_length=1, description="Stored document name.")


class CountDocumentsArguments(DoctypeArguments):
	filters: dict[str, Any] | list[Any] | None = Field(
		default=None, description="Equality filters or Frappe operator filters."
	)


class ListDocumentsArguments(CountDocumentsArguments):
	fields: list[str] | None = Field(default=None, description="List fields; defaults to name only.")
	order_by: str | None = Field(default=None, description="List order, such as creation desc.")
	start: int = Field(default=0, ge=0, description="List offset.")
	limit: int = Field(default=20, ge=1, description="List page size.")


class CreateDocumentArguments(DoctypeArguments):
	data: dict[str, Any] = Field(description="Field values. Put a custom document name inside data.")


class UpdateDocumentArguments(DocumentArguments):
	data: dict[str, Any] = Field(description="Field values to update.")


def get_document(doctype: str, name: str) -> dict:
	return {"document": v2.read_doc(doctype, name)}


def count_documents(doctype: str, filters: dict[str, Any] | list[Any] | None = None) -> dict:
	with form_dict({"filters": filters}):
		return {"doctype": doctype, "count": v2.count(doctype)}


def list_documents(
	doctype: str,
	filters: dict[str, Any] | list[Any] | None = None,
	fields: list[str] | None = None,
	order_by: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
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


def create_document(doctype: str, data: dict[str, Any]) -> dict:
	with form_dict(data):
		return {"action": "create", "document": v2.create_doc(doctype)}


def update_document(doctype: str, name: str, data: dict[str, Any]) -> dict:
	with form_dict(data):
		return {"action": "update", "document": v2.update_doc(doctype, name)}


def delete_document(doctype: str, name: str) -> dict:
	v2.delete_doc(doctype, name)
	return {"action": "delete", "doctype": doctype, "name": name}


LIST_DOCUMENTS = Tool(
	name="list_documents",
	description=(
		"List documents matching filters using your Frappe permissions. Fields default to name only. "
		"Start defaults to 0 and limit to 20. Use has_next_page to continue paging. "
		'Filters accept an object or operator lists such as [["status", "in", ["Open"]]]. '
		"Use get_doctype_schema to inspect fields."
	),
	arguments=ListDocumentsArguments,
	handler=list_documents,
	annotations={"readOnlyHint": True},
)

GET_DOCUMENT = Tool(
	name="get_document",
	description="Read one complete document, including permitted fields and child rows, using your Frappe permissions.",
	arguments=DocumentArguments,
	handler=get_document,
	annotations={"readOnlyHint": True},
)

COUNT_DOCUMENTS = Tool(
	name="count_documents",
	description="Count documents matching filters using your Frappe permissions, without fetching their contents.",
	arguments=CountDocumentsArguments,
	handler=count_documents,
	annotations={"readOnlyHint": True},
)

CREATE_DOCUMENT = Tool(
	name="create_document",
	description=(
		"Create one document using your Frappe permissions and normal validation and controller hooks. "
		"Put a custom document name inside data. Use get_doctype_schema to inspect required fields."
	),
	arguments=CreateDocumentArguments,
	handler=create_document,
	annotations={"destructiveHint": False, "idempotentHint": False},
)

UPDATE_DOCUMENT = Tool(
	name="update_document",
	description="Update one document using your Frappe permissions and normal validation and controller hooks.",
	arguments=UpdateDocumentArguments,
	handler=update_document,
	annotations={"destructiveHint": True, "idempotentHint": False},
)

DELETE_DOCUMENT = Tool(
	name="delete_document",
	description="Delete one document using your Frappe permissions and normal link checks and controller hooks.",
	arguments=DocumentArguments,
	handler=delete_document,
	annotations={"destructiveHint": True, "idempotentHint": False},
)
