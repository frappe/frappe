from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.set_value("Print Settings", "Print Settings", "allow_print_for_draft", 1)