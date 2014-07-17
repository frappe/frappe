# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "print_settings")
	frappe.db.set_value("Print Settings", "Print Settings", "print_style", "Modern")
	try:
		import pdfkit
	except ImportError:
		pass
	else:
		frappe.db.set_value("Print Settings", "Print Settings", "send_print_as_pdf", 1)
