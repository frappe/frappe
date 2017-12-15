# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	try:
		frappe.db.sql("alter table `tabEmail Queue` change `ref_docname` `reference_name` varchar(255)")
	except Exception as e:
		if e.args[0] not in (1054, 1060):
			raise

	try:
		frappe.db.sql("alter table `tabEmail Queue` change `ref_doctype` `reference_doctype` varchar(255)")
	except Exception as e:
		if e.args[0] not in (1054, 1060):
			raise
	frappe.reload_doctype("Email Queue")
