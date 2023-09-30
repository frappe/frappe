# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	if frappe.db.exists("Navbar Item", {"item_label": "App Launcher"}):
		return

	navbar_settings = frappe.get_single("Navbar Settings")
	settings_items = navbar_settings.settings_dropdown

	view_website_item_idx = -1
	for i, item in navbar_settings.settings_dropdown:
		if item.label == 'View Website':
			view_website_item_idx = i

	settings_items.insert(view_website_item_idx + 1, {
		"item_label": "App Launcher",
		"item_type": "Route",
		"route": "/apps",
		"is_standard": 1,
	})

	navbar_settings.settings_dropdown = settings_items
	navbar_settings.save()
