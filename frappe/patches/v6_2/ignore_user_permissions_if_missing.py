from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype("System Settings")
	system_settings = frappe.get_doc("System Settings")
	system_settings.flags.ignore_mandatory = 1
	system_settings.save()
