import json

import frappe
from frappe.utils.data import sbool


def document_list(doctype: str):
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
	return frappe.call(frappe.client.get_list, doctype, **frappe.form_dict)


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


def get_request_form_data():
	if frappe.form_dict.data is None:
		data = frappe.safe_decode(frappe.request.get_data())
	else:
		data = frappe.form_dict.data

	try:
		return frappe.parse_json(data)
	except ValueError:
		return frappe.form_dict
