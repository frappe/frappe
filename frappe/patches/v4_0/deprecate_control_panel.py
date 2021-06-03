# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def execute():
	frappe.db.sql("update `tabDefaultValue` set parenttype='__default' where parenttype='Control Panel'")
	frappe.db.sql("update `tabDefaultValue` set parent='__default' where parent='Control Panel'")
	frappe.clear_cache()
