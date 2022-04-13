from __future__ import unicode_literals

import frappe


def execute():
	frappe.reload_doctype("Letter Head")

	# source of all existing letter heads must be HTML
	frappe.db.sql("update `tabLetter Head` set source = 'HTML'")
