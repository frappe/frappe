# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Call existing APIs without changing their whitelist or permission rules."""

from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.mcp.tools import DocumentName, Tool, ToolArguments, form_dict


class CallMethodArguments(ToolArguments):
	method: str = Field(min_length=1)
	args: dict[str, Any] = Field(default_factory=dict)


class CallDocumentMethodArguments(CallMethodArguments):
	doctype: str = Field(min_length=1)
	name: DocumentName
	method: str = Field(min_length=1)


def call_method(method: str, args: dict[str, Any]) -> dict:
	with form_dict(args):
		result = v2.handle_rpc_call(method)
		if result is None:
			result = frappe.response.get("message", frappe.response.get("data"))
		return {"result": result}


def call_document_method(doctype: str, name: str, method: str, args: dict[str, Any]) -> dict:
	with form_dict(args):
		result = v2.execute_doc_method(doctype, name, method)
		return {"result": result, "document": frappe.response.docs[-1]}


CALL_METHOD = Tool(
	name="call_method",
	description="Call a whitelisted method by dotted path, or an API Server Script by name.",
	arguments=CallMethodArguments,
	handler=call_method,
	annotations={"destructiveHint": True},
)

CALL_DOCUMENT_METHOD = Tool(
	name="call_document_method",
	description="Call a whitelisted method of one document, such as submit or cancel.",
	arguments=CallDocumentMethodArguments,
	handler=call_document_method,
	annotations={"destructiveHint": True},
)
