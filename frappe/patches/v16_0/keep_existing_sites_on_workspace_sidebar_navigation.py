# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.navigation import DESKTOP_ICON_AND_WORKSPACE_SIDEBAR


def execute():
	"""Pin existing sites to the navigation they already have.

	The `navigation` field defaults to `Workspace`, so fresh installs get the new
	navigation. Upgrading sites must not have it change underneath them, so this moves
	them to `Desktop Icon and Workspace Sidebar`; they can opt in from System Settings.

	Fresh installs never run this -- `frappe.installer.set_all_patches_as_completed`
	marks every patch as done without executing it -- so the default stands there.
	"""
	frappe.reload_doc("core", "doctype", "system_settings")

	frappe.db.set_single_value("System Settings", "navigation", DESKTOP_ICON_AND_WORKSPACE_SIDEBAR)
	# Written explicitly because this bypasses SystemSettings.on_update, which is what
	# normally mirrors changed fields into defaults.
	frappe.db.set_default("navigation", DESKTOP_ICON_AND_WORKSPACE_SIDEBAR)

	frappe.clear_cache()
