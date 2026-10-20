# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Call existing APIs without changing their whitelist or permission rules."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.mcp.tools import DocumentName, Tool, ToolArguments, form_dict
from frappe.model.base_document import get_controller


class CallMethodArguments(ToolArguments):
	method: str = Field(min_length=1)
	args: dict[str, Any] = Field(default_factory=dict)


class CallDocumentMethodArguments(ToolArguments):
	doctype: str = Field(min_length=1)
	name: DocumentName
	method: str = Field(min_length=1)
	args: dict[str, Any] = Field(default_factory=dict)


def call_method(method: str, args: dict[str, Any]) -> dict:
	with form_dict(args), request_method(rpc_function(method)):
		result = v2.handle_rpc_call(method)
		if result is None:
			result = frappe.response.get("message", frappe.response.get("data"))
		return {"result": result}


def call_document_method(doctype: str, name: str, method: str, args: dict[str, Any]) -> dict:
	with form_dict(args), request_method(document_function(doctype, method)):
		result = v2.execute_doc_method(doctype, name, method)
		return {"result": result, "document": frappe.response.docs[-1]}


@contextmanager
def request_method(fn: Callable | None) -> Iterator[None]:
	"""Run a method whitelisted for GET but not POST as an HTTP GET runs it.

	A tool call has no HTTP method of its own. GET checks read permission and
	rolls back, so it grants nothing that the same call over HTTP does not.
	"""
	allowed = frappe.allowed_http_methods_for_whitelisted_func.get(fn, ())
	if "GET" not in allowed or "POST" in allowed:
		yield
		return

	request = frappe.local.request
	request.method = "GET"
	try:
		yield
	finally:
		request.method = "POST"
	if not frappe.local.flags.commit:
		frappe.db.rollback()


def rpc_function(method: str) -> Callable | None:
	method = frappe.override_whitelisted_method(method)
	if method in v2.get_server_script_map().get("_api", {}):
		return None
	try:
		return frappe.get_attr(method)
	except Exception:
		# `handle_rpc_call` reports the missing method.
		return None


def document_function(doctype: str, method: str) -> Callable | None:
	return getattr(get_controller(doctype), method, None)


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
