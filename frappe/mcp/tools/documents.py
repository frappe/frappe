# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Document tools reuse REST API v2 permissions and controller hooks."""

from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.mcp.tools import DocumentName, Tool, ToolArguments, form_dict


class GetDocumentArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	name: DocumentName


class CountDocumentsArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	filters: dict[str, Any] | list[Any] | None = None


class ListDocumentsArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	filters: dict[str, Any] | list[Any] | None = None
	fields: list[str] | None = None
	order_by: str | None = None
	start: int = Field(default=0, ge=0)
	limit: int = Field(default=20, ge=1)


class CreateDocumentArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	data: dict[str, Any]


class UpdateDocumentArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	name: DocumentName
	data: dict[str, Any]


class DeleteDocumentArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	name: DocumentName


def get_document(doctype: str, name: str) -> dict:
	return v2.read_doc(doctype, name)


def count_documents(doctype: str, filters: dict[str, Any] | list[Any] | None = None) -> int:
	with form_dict({"filters": filters}):
		return v2.count(doctype)


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
	return {"documents": documents, "has_next_page": has_next_page}


def create_document(doctype: str, data: dict[str, Any]) -> dict:
	with form_dict(data):
		return v2.create_doc(doctype)


def update_document(doctype: str, name: str, data: dict[str, Any]) -> dict:
	with form_dict(data):
		return v2.update_doc(doctype, name)


def delete_document(doctype: str, name: str) -> None:
	v2.delete_doc(doctype, name)


LIST_DOCUMENTS = Tool(
	name="list_documents",
	description="List documents like frappe.get_list.",
	arguments=ListDocumentsArguments,
	handler=list_documents,
	annotations={"readOnlyHint": True},
)

GET_DOCUMENT = Tool(
	name="get_document",
	description="Get one document with its child tables.",
	arguments=GetDocumentArguments,
	handler=get_document,
	annotations={"readOnlyHint": True},
)

COUNT_DOCUMENTS = Tool(
	name="count_documents",
	arguments=CountDocumentsArguments,
	handler=count_documents,
	annotations={"readOnlyHint": True},
)

CREATE_DOCUMENT = Tool(
	name="create_document",
	arguments=CreateDocumentArguments,
	handler=create_document,
	annotations={"destructiveHint": False},
)

UPDATE_DOCUMENT = Tool(
	name="update_document",
	arguments=UpdateDocumentArguments,
	handler=update_document,
	annotations={"destructiveHint": True},
)

DELETE_DOCUMENT = Tool(
	name="delete_document",
	arguments=DeleteDocumentArguments,
	handler=delete_document,
	annotations={"destructiveHint": True},
)
