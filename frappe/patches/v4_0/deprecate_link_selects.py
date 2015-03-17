# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for name in frappe.db.sql_list("""select name from `tabCustom Field`
		where fieldtype="Select" and options like "link:%" """):
		custom_field = frappe.get_doc("Custom Field", name)
		custom_field.fieldtype = "Link"
		custom_field.options = custom_field.options[5:]
		custom_field.save()
