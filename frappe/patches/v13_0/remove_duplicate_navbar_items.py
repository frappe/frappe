from __future__ import unicode_literals

import frappe


def execute():
	navbar_settings = frappe.get_single("Navbar Settings")
	duplicate_items = []

	for navbar_item in navbar_settings.settings_dropdown:
		if navbar_item.item_label == "Toggle Full Width":
			duplicate_items.append(navbar_item)

	if len(duplicate_items) > 1:
		navbar_settings.remove(duplicate_items[0])
		navbar_settings.save()
