from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype('Print Settings')
	frappe.db.set_value('Print Settings', 'Print Settings', 'repeat_header_footer', 1)
