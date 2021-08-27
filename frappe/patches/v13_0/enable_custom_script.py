# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def execute():
	"""Enable all the existing Client script"""

	frappe.db.sql("""
		UPDATE `tabClient Script` SET enabled=1
	""")