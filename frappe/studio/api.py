from typing import Literal

import frappe
from frappe import _
from frappe.model import display_fieldtypes, no_value_fields, table_fields


@frappe.whitelist()
def get_docname(doctype: str, filters: dict | str) -> dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	# remove name filter if it is dynamic or empty - for fetching a document while testing
	if "name" in filters and (filters["name"].startswith(":") or not filters["name"]):
		del filters["name"]

	document = frappe.get_list(doctype, filters=filters, pluck="name", limit=1)
	return document[0] if document else None

	return None


@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	# find the name field
	name_field = next((field for field in fields if field.fieldname == "name"), None)
	if not name_field:
		name_field = frappe._dict(
			{
				"fieldname": "name",
				"fieldtype": "Data",
				"label": "ID",
			}
		)
		fields.append(name_field)

	return [
		field
		for field in fields
		if field.fieldtype not in ((set(no_value_fields) | set(display_fieldtypes)) - set(table_fields))
	]


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	controller = get_controller(doctype)
	whitelisted_methods = []

	for method in controller.__dict__:
		if callable(getattr(controller, method)):
			try:
				is_whitelisted(getattr(controller, method))
				whitelisted_methods.append(method)
			except Exception:
				# not whitelisted
				continue

	return whitelisted_methods


@frappe.whitelist()
def get_sort_fields(doctype: str):
	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in no_value_fields]
	fields = [
		{
			"label": _(field.label),
			"value": field.fieldname,
			"fieldname": field.fieldname,
		}
		for field in fields
		if field.label and field.fieldname
	]

	standard_fields = [
		{"label": "Created On", "fieldname": "creation"},
		{"label": "Last Modified", "fieldname": "modified"},
		{"label": "Modified By", "fieldname": "modified_by"},
		{"label": "Owner", "fieldname": "owner"},
	]

	for field in standard_fields:
		field["label"] = _(field["label"])
		field["value"] = field["fieldname"]
		fields.append(field)

	return fields


@frappe.whitelist()
def check_app_permission() -> bool:
	if frappe.session.user == "Administrator":
		return True
	if frappe.has_permission("Studio App", ptype="write") and frappe.has_permission(
		"Studio Page", ptype="write"
	):
		return True
	return False
