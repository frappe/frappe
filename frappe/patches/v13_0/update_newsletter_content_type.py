# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc('email', 'doctype', 'Newsletter')
	frappe.db.sql("""
		UPDATE tabNewsletter
		SET content_type = 'Rich Text'
	""")
