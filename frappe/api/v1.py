import json

from werkzeug.routing import Rule

import frappe
from frappe import _
from frappe.utils.data import sbool


def handle_rpc_call(method: str):
	import frappe.handler

	# TODO: inline this weird circular calls
	frappe.form_dict.cmd = method
	return frappe.handler.handle()


def get_doc_list(doctype: str):
	if frappe.form_dict.get("fields"):
		frappe.form_dict["fields"] = json.loads(frappe.form_dict["fields"])

	# set limit of records for frappe.get_list
	frappe.form_dict.setdefault(
		"limit_page_length",
		frappe.form_dict.limit or frappe.form_dict.limit_page_length or 20,
	)

	# convert strings to native types - only as_dict and debug accept bool
	for param in ["as_dict", "debug"]:
		param_val = frappe.form_dict.get(param)
		if param_val is not None:
			frappe.form_dict[param] = sbool(param_val)

	# evaluate frappe.get_list
	data = frappe.call(frappe.client.get_list, doctype, **frappe.form_dict)

	# set frappe.get_list result to response
	frappe.response.update({"data": data})


def create_doc(doctype: str):
	data = get_request_form_data()
	data.update({"doctype": doctype})

	# insert document from request data
	doc = frappe.get_doc(data).insert()

	# set response data
	frappe.response.update({"data": doc.as_dict()})


def read_doc(doctype: str, name: str):
	# Backward compatiblity
	if "run_method" in frappe.form_dict:
		execute_doc_method(doctype, name)
		return

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
	# Not checking permissions here because it's checked in delete_doc
	frappe.delete_doc(doctype, name, ignore_missing=False)
	frappe.response.http_status_code = 202
	frappe.response.message = "ok"


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
	Rule("/resource/<string:doctype>", methods=["GET"], endpoint=get_doc_list),
	Rule("/resource/<string:doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["GET"], endpoint=read_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["PUT"], endpoint=update_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["DELETE"], endpoint=delete_doc),
	Rule("/resource/<string:doctype>/<string:name>", methods=["POST"], endpoint=execute_doc_method),
]
