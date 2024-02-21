import frappe


def execute():
	item = frappe.db.exists("Navbar Item", {"item_label": "Background Jobs"})
	if not item:
		return

	frappe.delete_doc("Navbar Item", item)
