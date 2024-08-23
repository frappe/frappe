import frappe


def execute():
	for name in ("desktop", "space"):
		frappe.delete_doc("Page", name)
