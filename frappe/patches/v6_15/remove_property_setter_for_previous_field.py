# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("""delete from `tabProperty Setter` where property='previous_field'""")
	
	for d in frappe.db.sql("""select name from `tabCustom Field` 
		where insert_after is not null and insert_after != ''"""):
			try:
				frappe.get_doc("Custom Field", d[0]).set_property_setter_for_idx()
			except frappe.DoesNotExistError:
				pass