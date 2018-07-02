# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	try:
		frappe.db.sql("alter table `tabEmail Queue` change `ref_docname` `reference_name` varchar(255)")
	except Exception as e:
		if not frappe.db.is_table_or_column_missing(e):
			raise

	try:
		frappe.db.sql("alter table `tabEmail Queue` change `ref_doctype` `reference_doctype` varchar(255)")
	except Exception as e:
		if not frappe.db.is_table_or_column_missing(e):
			raise
	frappe.reload_doctype("Email Queue")
