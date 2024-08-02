# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe


def execute():
	if frappe.db.exists("Navbar Item", {"item_label": "Apps"}):
		return

	navbar_settings = frappe.get_single("Navbar Settings")
	settings_items = navbar_settings.as_dict().settings_dropdown

	view_website_item_idx = -1
	for i, item in enumerate(navbar_settings.settings_dropdown):
		if item.get("item_label") == "View Website":
			view_website_item_idx = i

	settings_items.insert(
		view_website_item_idx + 1,
		{
			"item_label": "Apps",
			"item_type": "Route",
			"route": "/apps",
			"is_standard": 1,
		},
	)

	navbar_settings.set("settings_dropdown", settings_items)
	navbar_settings.save()
