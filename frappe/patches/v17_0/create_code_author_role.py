# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe


def execute():
	if not frappe.db.exists("Role", "Code Author"):
		frappe.get_doc({"doctype": "Role", "role_name": "Code Author"}).insert(ignore_permissions=True)
