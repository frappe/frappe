# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for d in frappe.db.sql("""select name, dt, insert_after from `tabCustom Field`
		where docstatus < 2""", as_dict=1):
			dt_meta = frappe.get_meta(d.dt)
			if not dt_meta.get_field(d.insert_after):
				cf = frappe.get_doc("Custom Field", d.name)
				df = dt_meta.get("fields", {"label": d.insert_after})
				if df:
					cf.insert_after = df[0].fieldname
				else:
					cf.insert_after = None
				cf.save()
