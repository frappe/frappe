# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "outgoing_email_settings")
	try:
		import pdfkit
	except ImportError:
		pass
	else:
		frappe.db.set_value("Outgoing Email Settings", "Outgoing Email Settings", "send_print_as_pdf", 1)
