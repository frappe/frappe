# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The `call_method` tool: the escape hatch onto every whitelisted method."""

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _, is_whitelisted
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.handler import run_server_script
from frappe.mcp.tools import Tool, form_dict

DESCRIPTION = """Call a whitelisted method on this Frappe site. This is the escape hatch: whatever the other tools do not cover, this does.

Two forms:
- an RPC method: give the dotted 'method' path and its 'args'.
- a DocType method: give 'doctype', 'name' and the 'method' name.

It covers reports (frappe.desk.query_report.run), read-only SQL through the
System Console, file upload, the submit and cancel lifecycle actions, and every
method an installed app whitelists.

Call discover with the same method first to read its parameters."""

INPUT_SCHEMA = {
	"type": "object",
	"properties": {
		"method": {
			"type": "string",
			"description": (
				"A dotted RPC path, such as 'frappe.client.get_count'. "
				"With 'doctype' and 'name', a controller method name instead, such as 'submit'."
			),
		},
		"doctype": {"type": "string", "description": "The DocType, for a DocType method."},
		"name": {"type": "string", "description": "The document to run the method on."},
		"args": {"type": "object", "description": "Arguments for the method."},
	},
	"required": ["method"],
	"additionalProperties": False,
}


def call_method(arguments: dict[str, Any]) -> dict[str, Any]:
	method = arguments.get("method")
	if not method:
		frappe.throw("'method' is required", frappe.ValidationError)

	doctype = arguments.get("doctype")
	name = arguments.get("name")
	args = arguments.get("args") or {}

	if doctype and name:
		return _run_document_method(doctype, name, method, args)

	return {"method": method, "result": _run_rpc(method, doctype, args)}


def _run_rpc(method: str, doctype: str | None, args: dict[str, Any]) -> Any:
	"""Mirror `handle_rpc_call` from the API v2."""
	from frappe.modules.utils import load_doctype_module

	if doctype:
		# Expand to run the actual method from the doctype controller.
		module = load_doctype_module(doctype)
		method = module.__name__ + "." + method

	method = frappe.override_whitelisted_method(method)

	if server_script := get_server_script_map().get("_api", {}).get(method):
		with form_dict(args):
			return run_server_script(server_script)

	try:
		fn = frappe.get_attr(method)
	except frappe.AppNotInstalledError:
		raise
	except Exception as e:
		frappe.throw(_("Failed to get method {0} with {1}").format(method, str(e)))

	is_whitelisted(fn)
	_check_http_method(fn)

	with form_dict(args) as arguments:
		return frappe.call(fn, **arguments)


def _run_document_method(doctype: str, name: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
	"""Mirror `execute_doc_method` from the API v2."""
	doc = frappe.get_doc(doctype, name)
	doc.is_whitelisted(method)

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	doc.check_permission(_check_http_method(fn))

	with form_dict(args) as arguments:
		result = doc.run_method(method, **arguments)

	doc.apply_fieldlevel_read_permissions()
	return {"doctype": doctype, "name": name, "method": method, "result": result, "document": doc.as_dict()}


def _check_http_method(fn: Callable) -> str:
	"""Check the method against its allowed HTTP methods, and map that to a permission.

	`is_valid_http_method` reads `frappe.request.method`, which is always POST on
	this endpoint, so it would reject every GET-only method. Read the allow-list
	directly instead, and map it the way `PERMISSION_MAP` in the API v2 does.
	"""
	allowed = set(frappe.allowed_http_methods_for_whitelisted_func.get(fn, ()))
	if not allowed & {"GET", "POST"}:
		frappe.throw_permission_error()

	return "write" if "POST" in allowed else "read"


CALL_METHOD = Tool(
	name="call_method",
	title="Call a whitelisted method",
	description=DESCRIPTION,
	input_schema=INPUT_SCHEMA,
	annotations={"destructiveHint": True, "idempotentHint": False},
	handler=call_method,
)
