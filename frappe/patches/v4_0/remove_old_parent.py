# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for doctype in frappe.db.sql_list("""select name from `tabDocType` where istable=1"""):
		frappe.db.sql("""delete from `tab{0}` where parent like "old_par%:%" """.format(doctype))
	frappe.db.sql("""delete from `tabDocField` where parent="0" """)
