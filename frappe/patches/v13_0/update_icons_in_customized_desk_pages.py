import frappe


def execute():
	if not frappe.db.exists("Desk Page"):
		return

	pages = frappe.get_all(
		"Desk Page", filters={"is_standard": False}, fields=["name", "extends", "for_user"]
	)
	default_icon = {}
	for page in pages:
		if page.extends and page.for_user:
			if not default_icon.get(page.extends):
				default_icon[page.extends] = frappe.db.get_value("Desk Page", page.extends, "icon")

			icon = default_icon.get(page.extends)
			frappe.db.set_value("Desk Page", page.name, "icon", icon)
