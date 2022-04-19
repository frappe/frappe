from __future__ import unicode_literals

import frappe


def execute():
	frappe.reload_doctype("System Settings")
	doc = frappe.get_single("System Settings")
	doc.enable_chat = 1

	# Changes prescribed by Nabin Hait (nabin@frappe.io)
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True

	doc.save()
