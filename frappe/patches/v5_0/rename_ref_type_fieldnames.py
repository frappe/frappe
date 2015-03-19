# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("alter table `tabBulk Email` change `ref_docname` `reference_name` varchar(255)")
	frappe.db.sql("alter table `tabBulk Email` change `reference_doctype` `reference_doctype` varchar(255)")
	frappe.reload_doctype("Bulk Email")
