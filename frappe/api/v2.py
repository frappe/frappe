from werkzeug.routing import Rule

import frappe
from frappe import _
from frappe.api.utils import create_doc, delete_doc, document_list, update_doc


def handle_rpc_call(method: str, doctype: str | None = None):
	from frappe.handler import execute_cmd
	from frappe.modules.utils import load_doctype_module

	if doctype:
		# Expand to run actual method
		module = load_doctype_module(doctype)
		method = module.__name__ + "." + method

	if method == "login":
		return

	return execute_cmd(method)


def read_doc(doctype: str, name: str):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	return doc


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	method = method or frappe.form_dict.pop("run_method")
	doc = frappe.get_doc(doctype, name)
	doc.is_whitelisted(method)

	if frappe.request.method == "GET":
		doc.check_permission("read")
		return doc.run_method(method, **frappe.form_dict)

	elif frappe.request.method == "POST":
		doc.check_permission("write")
		return doc.run_method(method, **frappe.form_dict)


url_rules = [
	Rule("/method/<string:method>", endpoint=handle_rpc_call),
	Rule("/method/<string:doctype>/<string:method>", endpoint=handle_rpc_call),
	Rule("/resource/<string:doctype>", methods=["GET"], endpoint=document_list),
	Rule("/resource/<string:doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["GET"], endpoint=read_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["PUT"], endpoint=update_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["DELETE"], endpoint=delete_doc),
	Rule(
		"/resource/<string:doctype>/<string:name>/<string:method>",
		methods=["GET", "POST"],
		endpoint=execute_doc_method,
	),
]
