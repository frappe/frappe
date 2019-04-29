# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe

def add_custom_field(doctype, fieldname, fieldtype='Data', options=None, default=None, depends_on=None):
	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": doctype,
		"fieldname": fieldname,
		"fieldtype": fieldtype,
		"options": options,
		"default": default,
		"depends_on": depends_on
	}).insert()

def clear_custom_fields(doctype):
	frappe.db.sql('delete from `tabCustom Field` where dt=%s', doctype)
	frappe.clear_cache(doctype=doctype)
