# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def execute():
	frappe.reload_doc("core", "doctype", "system_settings")
	frappe.db.set_value('System Settings', None, "allow_login_after_fail", 60)