# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "print_settings")
	print_settings = frappe.get_doc("Print Settings")
	print_settings.with_letterhead = 1
	print_settings.save()
