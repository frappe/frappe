# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	attach_fields = (frappe.db.sql("""select parent, fieldname from `tabDocField` where fieldtype in ('Attach', 'Attach Image')""") +
		frappe.db.sql("""select dt, fieldname from `tabCustom Field` where fieldtype in ('Attach', 'Attach Image')"""))

	for doctype, fieldname in attach_fields:
		frappe.db.sql("""update `tab{doctype}` set `{fieldname}`=concat("/", `{fieldname}`)
			where `{fieldname}` like 'files/%'""".format(doctype=doctype, fieldname=fieldname))
