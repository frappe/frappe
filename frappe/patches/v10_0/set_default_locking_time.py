# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	frappe.reload_doc("core", "doctype", "system_settings")
	frappe.db.set_single_value("System Settings", "allow_login_after_fail", 60)
