# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import DESKTOP_ICONS


def execute():
	"""Keep the desktop that upgrading sites already have -- where they have one.

	The `desktop_page` field defaults to `Apps`, so fresh installs get the new apps screen.
	A site that was already on the `Desktop Icon` grid is moved back to it: an upgrade
	shouldn't change their desktop underneath them; they can switch from Desktop Settings.

	Holding icon rows is what "already on the grid" means. Nothing seeds them unless the
	site is on that page (`create_desktop_icons` is gated on it), so their presence is the
	site's own answer. A v15 site has none and never saw a grid, and pinning it there
	unconditionally handed the customer an empty screen with nothing to arrange -- the
	condition is what makes "don't change their desktop underneath them" true for them too.

	`Desktop Icon` long predates that grid, so "has rows" would otherwise also be true of a
	site carrying icons from the v12-era desktop. It isn't, because `patches.txt` truncates
	the table in `[pre_model_sync]` -- ahead of this -- which is the line that makes those
	rows mean the grid and nothing else. Don't move this above it.

	Fresh installs never run this: `frappe.installer.set_all_patches_as_completed` marks
	every patch as done without executing it, so the `Apps` default stands there.
	"""
	frappe.reload_doc("desk", "doctype", "desktop_settings")

	if not frappe.db.exists("Desktop Icon", {}):
		return

	frappe.db.set_single_value("Desktop Settings", "desktop_page", DESKTOP_ICONS)
	frappe.clear_cache()
