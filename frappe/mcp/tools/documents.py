# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Document tools reuse REST API v2 permissions and controller hooks."""

from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.mcp.tools import DocumentName, Tool, ToolArguments, form_dict

BATCH_LIMIT = 20


class DoctypeArguments(ToolArguments):
	doctype: str = Field(min_length=1)


class DocumentArguments(DoctypeArguments):
	name: DocumentName


class CountDocumentsArguments(DoctypeArguments):
	filters: dict[str, Any] | list[Any] | None = None


class ListDocumentsArguments(CountDocumentsArguments):
	fields: list[str] | None = None
	order_by: str | None = None
	start: int = Field(default=0, ge=0)
	limit: int = Field(default=20, ge=1)


class CreateDocumentsArguments(DoctypeArguments):
	documents: list[dict[str, Any]] = Field(min_length=1, max_length=BATCH_LIMIT)


class DocumentUpdate(ToolArguments):
	name: DocumentName
	data: dict[str, Any]


class UpdateDocumentsArguments(DoctypeArguments):
	documents: list[DocumentUpdate] = Field(min_length=1, max_length=BATCH_LIMIT)


class DeleteDocumentsArguments(DoctypeArguments):
	names: list[DocumentName] = Field(min_length=1, max_length=BATCH_LIMIT)


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


def create_documents(doctype: str, documents: list[dict[str, Any]]) -> dict:
	names = []
	for data in documents:
		with form_dict(data):
			names.append(v2.create_doc(doctype)["name"])
	return {"names": names}


def update_documents(doctype: str, documents: list[dict[str, Any]]) -> dict:
	names = []
	for document in documents:
		with form_dict(document["data"]):
			names.append(v2.update_doc(doctype, document["name"])["name"])
	return {"names": names}


def delete_documents(doctype: str, names: list[str]) -> dict:
	for name in names:
		v2.delete_doc(doctype, name)
	return {"names": names}


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
	arguments=DocumentArguments,
	handler=get_document,
	annotations={"readOnlyHint": True},
)

COUNT_DOCUMENTS = Tool(
	name="count_documents",
	arguments=CountDocumentsArguments,
	handler=count_documents,
	annotations={"readOnlyHint": True},
)

CREATE_DOCUMENTS = Tool(
	name="create_documents",
	arguments=CreateDocumentsArguments,
	handler=create_documents,
	annotations={"destructiveHint": False},
)

UPDATE_DOCUMENTS = Tool(
	name="update_documents",
	arguments=UpdateDocumentsArguments,
	handler=update_documents,
	annotations={"destructiveHint": True},
)

DELETE_DOCUMENTS = Tool(
	name="delete_documents",
	arguments=DeleteDocumentsArguments,
	handler=delete_documents,
	annotations={"destructiveHint": True},
)
