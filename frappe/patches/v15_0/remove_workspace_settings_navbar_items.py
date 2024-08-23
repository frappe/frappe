import frappe


def execute():
	navbar_settings = frappe.get_single("Navbar Settings")

	# Remove "Workspace Settings" item from version 15
	workspace_item = next(
		(item for item in navbar_settings.settings_dropdown if item.item_label == "Workspace Settings"), None
	)

	if workspace_item:
		navbar_settings.settings_dropdown.remove(workspace_item)

	for idx, item in enumerate(navbar_settings.settings_dropdown, start=1):
		item.idx = idx

	navbar_settings.save()
