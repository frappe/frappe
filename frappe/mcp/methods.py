"""Adapt a logical REST verb while preserving API v2 whitelist checks."""

from werkzeug.wrappers import Response

import frappe
from frappe import _
from frappe.api import v2
from frappe.modules.utils import load_doctype_module


def execute_method(method, doctype, name, http_method):
	if name and not doctype:
		frappe.throw(_("A DocType is required with a document name"))
	if doctype and name:
		doc = frappe.get_doc(doctype, name)
		doc.is_whitelisted(method)
		fn = getattr(doc, method)
		fn = getattr(fn, "__func__", fn)
	else:
		path = f"{load_doctype_module(doctype).__name__}.{method}" if doctype else method
		path = frappe.override_whitelisted_method(path)
		from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

		fn = None if get_server_script_map().get("_api", {}).get(path) else frappe.get_attr(path)
		if fn:
			frappe.is_whitelisted(fn)

	allowed = set(frappe.allowed_http_methods_for_whitelisted_func.get(fn, ()))
	verb = http_method or ("GET" if "GET" in allowed and allowed <= {"GET", "QUERY"} else "POST")
	if doctype and name and verb not in v2.PERMISSION_MAP:
		frappe.throw(_("Document methods support GET, POST, or QUERY"))
	# API v2 checks the selected verb and the corresponding document permission.
	frappe.request.method = verb
	value = (
		v2.execute_doc_method(doctype, name, method)
		if doctype and name
		else v2.handle_rpc_call(method, doctype)
	)
	if isinstance(value, Response) or frappe.response.get("type") not in (None, "json"):
		frappe.throw(_("MCP methods must return JSON data"))
	return {"method": method, "result": value, "documents": frappe.response.get("docs", [])}
