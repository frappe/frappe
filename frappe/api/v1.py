import json

from werkzeug.routing import Rule

import frappe
from frappe import _
from frappe.utils import attach_expanded_links
from frappe.utils.data import sbool


def document_list(doctype: str):
	if frappe.form_dict.get("fields"):
		frappe.form_dict["fields"] = json.loads(frappe.form_dict["fields"])

	if frappe.form_dict.get("expand"):
		frappe.form_dict["expand"] = json.loads(frappe.form_dict["expand"])

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
	return frappe.call(frappe.client.get_list, doctype, **frappe.form_dict)


def handle_rpc_call(method: str):
	import frappe.handler

	method = method.split("/")[0]  # for backward compatiblity

	frappe.form_dict.cmd = method
	return frappe.handler.handle()


def create_doc(doctype: str):
	data = get_request_form_data()
	data.pop("doctype", None)
	return frappe.new_doc(doctype, **data).insert()


def update_doc(doctype: str, name: str):
	data = get_request_form_data()

	doc = frappe.get_doc(doctype, name, for_update=True)
	if "flags" in data:
		del data["flags"]

	doc.update(data)
	doc.save()

	# check for child table doctype
	if doc.get("parenttype"):
		frappe.get_doc(doc.parenttype, doc.parent).save()

	return doc


def delete_doc(doctype: str, name: str):
	# TODO: child doc handling
	frappe.delete_doc(doctype, name, ignore_missing=False)
	frappe.response.http_status_code = 202
	return "ok"


def read_doc(doctype: str, name: str):
	# Backward compatiblity
	if "run_method" in frappe.form_dict:
		return execute_doc_method(doctype, name)

	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError
	doc.apply_fieldlevel_read_permissions()
	doc_dict = doc.as_dict()
	if sbool(frappe.form_dict.get("expand_links")):
		get_values_for_link_and_dynamic_link_fields(doc_dict)
		get_values_for_table_and_multiselect_fields(doc_dict)

	return doc_dict


def get_values_for_link_and_dynamic_link_fields(doc_dict):
	meta = frappe.get_meta(doc_dict.doctype)
	link_fields = meta.get_link_fields() + meta.get_dynamic_link_fields()

	for field in link_fields:
		if not (doc_fieldvalue := getattr(doc_dict, field.fieldname, None)):
			continue

		doctype = field.options if field.fieldtype == "Link" else doc_dict.get(field.options)

		link_doc = frappe.get_doc(doctype, doc_fieldvalue)
		doc_dict.update({field.fieldname: link_doc})


def get_values_for_table_and_multiselect_fields(doc_dict):
	meta = frappe.get_meta(doc_dict.doctype)
	table_fields = meta.get_table_fields()

	for field in table_fields:
		table_link_fieldnames = [f.fieldname for f in frappe.get_meta(field.options).get_link_fields()]
		attach_expanded_links(field.options, doc_dict.get(field.fieldname), table_link_fieldnames)


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
	Rule("/method/<path:method>", endpoint=handle_rpc_call),
	Rule("/resource/<doctype>", methods=["GET"], endpoint=document_list),
	Rule("/resource/<doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["GET"], endpoint=read_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["PUT"], endpoint=update_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["DELETE"], endpoint=delete_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["POST"], endpoint=execute_doc_method),
]
