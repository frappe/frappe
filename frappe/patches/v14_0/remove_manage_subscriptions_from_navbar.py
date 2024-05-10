import frappe


def execute():
	navbar_settings = frappe.get_single("Navbar Settings")
	for i, l in enumerate(navbar_settings.settings_dropdown):
		if l.item_label == "Manage Subscriptions":
			navbar_settings.settings_dropdown.pop(i)
			navbar_settings.save()
			break
