# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	"""Enable all the existing custom script"""
	frappe.reload_doc("Custom", "doctype", "Custom Script")

	frappe.db.sql("""
		UPDATE `tabCustom Script` SET enabled=1
	""")