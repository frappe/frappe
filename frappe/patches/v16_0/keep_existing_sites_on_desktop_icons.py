# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import DESKTOP_ICONS


def execute():
	"""Keep the desktop that upgrading sites already have.

	The `desktop_page` field defaults to `Apps`, so fresh installs get the new apps screen.
	Existing sites had the desktop icon grid, so move them to `Desktop Icons` -- an upgrade
	shouldn't change their desktop underneath them; they can switch from Desktop Settings.

	Fresh installs never run this: `frappe.installer.set_all_patches_as_completed` marks
	every patch as done without executing it, so the `Apps` default stands there.
	"""
	frappe.reload_doc("desk", "doctype", "desktop_settings")
	frappe.db.set_single_value("Desktop Settings", "desktop_page", DESKTOP_ICONS)
	frappe.clear_cache()
