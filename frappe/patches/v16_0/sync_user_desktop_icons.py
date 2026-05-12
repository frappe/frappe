# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	from frappe.desk.doctype.desktop_icon.desktop_icon import sync_all_user_layouts

	sync_all_user_layouts()
