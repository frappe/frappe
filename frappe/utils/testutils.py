# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe


def add_custom_field(doctype, fieldname, fieldtype="Data", options=None):
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": fieldname,
			"fieldtype": fieldtype,
			"options": options,
		}
	).insert()


def clear_custom_fields(doctype):
	frappe.db.delete("Custom Field", {"dt": doctype})
	frappe.clear_cache(doctype=doctype)
