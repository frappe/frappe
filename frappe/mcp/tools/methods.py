# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Call existing APIs without changing their whitelist or permission rules."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Self

from pydantic import Field, model_validator

import frappe
from frappe import _
from frappe.api import v2
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.mcp.tools import Tool, ToolArguments, form_dict
from frappe.modules.utils import load_doctype_module


class CallMethodArguments(ToolArguments):
	method: str = Field(min_length=1, description="Dotted API path or a controller method name.")
	doctype: str | None = Field(default=None, min_length=1, description="Controller's DocType.")
	name: str | None = Field(default=None, min_length=1, description="Stored document to call the method on.")
	args: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the method.")

	@model_validator(mode="after")
	def check_document(self) -> Self:
		if self.name is not None and self.doctype is None:
			raise ValueError(_("doctype is required when name is supplied"))
		return self


def call_method(
	method: str, doctype: str | None = None, name: str | None = None, args: dict[str, Any] | None = None
) -> dict:
	with form_dict(args or {}):
		if name is not None:
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

		path = f"{load_doctype_module(doctype).__name__}.{method}" if doctype else method
		overridden = frappe.override_whitelisted_method(path)
		if get_server_script_map().get("_api", {}).get(overridden):
			result = v2.handle_rpc_call(path)
		else:
			fn = frappe.get_attr(overridden)
			frappe.is_whitelisted(fn)
			with method_request(fn):
				result = v2.handle_rpc_call(path)
		if result is None:
			result = frappe.response.get("message", frappe.response.get("data"))
		return {"method": method, "result": result}


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
		"Call an existing whitelisted Frappe API with args. Supply a dotted method path for an API, "
		"doctype and method for a controller module function, or doctype, name and method for a "
		"stored document method, including submit or cancel. Frappe validates method arguments. "
		"GET-only document methods require read access; methods allowing POST require write access "
		"and their own operation permissions. Other HTTP-only methods are unsupported. "
		"Whitelisting does not grant document access or replace the API's permission checks. "
		"Database changes roll back on failure unless the method commits explicitly; immediate "
		"external effects cannot be undone. Method discovery requires System Manager access."
	),
	arguments=CallMethodArguments,
	handler=call_method,
	annotations={"destructiveHint": True, "idempotentHint": False},
)
