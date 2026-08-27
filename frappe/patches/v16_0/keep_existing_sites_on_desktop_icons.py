# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import DESKTOP_ICONS


def execute():
	"""Keep the desktop that upgrading sites already have, where they have one.

	The `desktop_page` field defaults to `Apps`, so fresh installs get the new apps screen. A site
	that was already on the `Desktop Icon` grid is moved back to it: an upgrade should not change
	their desktop underneath them, and they can switch from Desktop Settings.

	"""
	if not frappe.db.get_all("Desktop Icon", limit=1):
		return

	frappe.db.set_single_value("Desktop Settings", "desktop_page", DESKTOP_ICONS)
	frappe.clear_cache()
