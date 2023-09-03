from werkzeug.routing import Rule

import frappe
from frappe import _
from frappe.api.utils import create_doc, delete_doc, document_list, update_doc


def handle_rpc_call(method: str):
	import frappe.handler

	frappe.form_dict.cmd = method
	return frappe.handler.handle()


def read_doc(doctype: str, name: str):
	# Backward compatiblity
	if "run_method" in frappe.form_dict:
		return execute_doc_method(doctype, name)

	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError
	doc.apply_fieldlevel_read_permissions()
	return doc


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	method = method or frappe.form_dict.pop("run_method")
	doc = frappe.get_doc(doctype, name)
	doc.is_whitelisted(method)

	if frappe.request.method == "GET":
		if not doc.has_permission("read"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return doc.run_method(method, **frappe.form_dict)

	elif frappe.request.method == "POST":
		if not doc.has_permission("write"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		return doc.run_method(method, **frappe.form_dict)


def get_request_form_data():
	if frappe.form_dict.data is None:
		data = frappe.safe_decode(frappe.request.get_data())
	else:
		data = frappe.form_dict.data

	try:
		return frappe.parse_json(data)
	except ValueError:
		return frappe.form_dict


url_rules = [
	Rule("/method/<string:method>", endpoint=handle_rpc_call),
	Rule("/resource/<string:doctype>", methods=["GET"], endpoint=document_list),
	Rule("/resource/<string:doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["GET"], endpoint=read_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["PUT"], endpoint=update_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["DELETE"], endpoint=delete_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["POST"], endpoint=execute_doc_method),
]
