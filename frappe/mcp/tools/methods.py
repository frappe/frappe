# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Call existing APIs without changing their whitelist or permission rules."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pydantic import Field

import frappe
from frappe.api import v2
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.mcp.tools import Tool, ToolArguments, form_dict


class CallMethodArguments(ToolArguments):
	method: str = Field(min_length=1, description="Full dotted API path or API Server Script name.")
	args: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the method.")


class CallDocumentMethodArguments(CallMethodArguments):
	doctype: str = Field(min_length=1, description="Document's DocType.")
	name: str = Field(min_length=1, description="Stored document to call the method on.")
	method: str = Field(min_length=1, description="Whitelisted document instance method name.")


def call_method(method: str, args: dict[str, Any]) -> dict:
	with form_dict(args):
		overridden = frappe.override_whitelisted_method(method)
		if get_server_script_map().get("_api", {}).get(overridden):
			result = v2.handle_rpc_call(method)
		else:
			fn = frappe.get_attr(overridden)
			frappe.is_whitelisted(fn)
			with method_request(fn):
				result = v2.handle_rpc_call(method)
		if result is None:
			result = frappe.response.get("message", frappe.response.get("data"))
		return {"method": method, "result": result}


def call_document_method(doctype: str, name: str, method: str, args: dict[str, Any]) -> dict:
	with form_dict(args):
		doc = frappe.get_doc(doctype, name)
		doc.is_whitelisted(method)
		with method_request(getattr(doc, method)):
			result = v2.execute_doc_method(doctype, name, method)
		return {
			"doctype": doctype,
			"name": name,
			"method": method,
			"result": result,
			"document": frappe.response.docs[-1],
		}


@contextmanager
def method_request(fn: Callable) -> Iterator[None]:
	"""Adapt the POST transport to REST's GET-only methods and restore it afterwards."""
	fn = getattr(fn, "__func__", fn)
	allowed = frappe.allowed_http_methods_for_whitelisted_func.get(fn, ())
	if "POST" in allowed:
		method = "POST"
	elif "GET" in allowed:
		method = "GET"
	else:
		frappe.throw_permission_error()
	request = frappe.local.request
	original_method = request.method
	request.method = method
	try:
		yield
	finally:
		request.method = original_method


CALL_METHOD = Tool(
	name="call_method",
	description=(
		"Call a whitelisted Frappe API function by full dotted path, or an API Server Script by name. "
		"Controller module functions also use their full dotted path. Frappe validates args. "
		"Whitelisting does not replace the API's permission checks. GET and POST methods are supported. "
		"Explicit commits and immediate external effects cannot be undone after failure."
	),
	arguments=CallMethodArguments,
	handler=call_method,
	annotations={"destructiveHint": True, "idempotentHint": False},
)

CALL_DOCUMENT_METHOD = Tool(
	name="call_document_method",
	description=(
		"Call a whitelisted instance method on one stored document, including submit or cancel. "
		"Frappe validates args. GET-only methods require read access; methods allowing POST require "
		"write access and their own operation permissions. Other HTTP-only methods are unsupported. "
		"Explicit commits and immediate external effects cannot be undone after failure."
	),
	arguments=CallDocumentMethodArguments,
	handler=call_document_method,
	annotations={"destructiveHint": True, "idempotentHint": False},
)
