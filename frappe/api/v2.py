import json

from werkzeug.routing import Rule
from werkzeug.wrappers import Response

import frappe
from frappe import _
from frappe.api.utils import document_list
from frappe.utils.data import sbool


def handle_rpc_call(method: str, doctype: str | None = None):
	from frappe.handler import execute_cmd
	from frappe.modules.utils import load_doctype_module

	if doctype:
		# Expand to run actual method
		module = load_doctype_module(doctype)
		method = module.__name__ + "." + method

	if method == "login":
		return

	data = execute_cmd(method)
	if isinstance(data, Response):
		# method returns a response object, pass it on
		return data

	frappe.response["data"] = data


def get_doc_list(doctype: str):
	frappe.response.update({"data": document_list(doctype)})


def create_doc(doctype: str):
	data = get_request_form_data()
	data.update({"doctype": doctype})

	# insert document from request data
	doc = frappe.get_doc(data).insert()

	# set response data
	frappe.response.update({"data": doc.as_dict()})


def read_doc(doctype: str, name: str):
	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError
	doc.apply_fieldlevel_read_permissions()
	frappe.response.update({"data": doc})


def update_doc(doctype: str, name: str):
	data = get_request_form_data()

	doc = frappe.get_doc(doctype, name, for_update=True)

	if "flags" in data:
		del data["flags"]

	# Not checking permissions here because it's checked in doc.save
	doc.update(data)

	frappe.response.update({"data": doc.save().as_dict()})

	# check for child table doctype
	if doc.get("parenttype"):
		frappe.get_doc(doc.parenttype, doc.parent).save()


def delete_doc(doctype: str, name: str):
	frappe.delete_doc(doctype, name, ignore_missing=False)
	frappe.response.http_status_code = 202


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	method = method or frappe.form_dict.pop("run_method")
	doc = frappe.get_doc(doctype, name)
	doc.is_whitelisted(method)

	if frappe.request.method == "GET":
		if not doc.has_permission("read"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		frappe.response.update({"data": doc.run_method(method, **frappe.form_dict)})

	elif frappe.request.method == "POST":
		if not doc.has_permission("write"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		frappe.response.update({"data": doc.run_method(method, **frappe.form_dict)})


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
	Rule("/method/<string:doctype>/<string:method>", endpoint=handle_rpc_call),
	Rule("/resource/<string:doctype>", methods=["GET"], endpoint=get_doc_list),
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
