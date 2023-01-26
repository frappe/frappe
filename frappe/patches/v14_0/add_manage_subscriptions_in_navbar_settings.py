import frappe


def execute():
	navbar_settings = frappe.get_single("Navbar Settings")

	if frappe.db.exists("Navbar Item", {"item_label": "Manage Subscriptions"}):
		return

	for idx, row in enumerate(navbar_settings.settings_dropdown[2:], start=4):
		row.idx = idx

	navbar_settings.append(
		"settings_dropdown",
		{
			"item_label": "Manage Subscriptions",
			"item_type": "Action",
			"action": "frappe.ui.toolbar.redirectToUrl()",
			"is_standard": 1,
			"hidden": 1,
			"idx": 3,
		},
	)

	navbar_settings.save()
