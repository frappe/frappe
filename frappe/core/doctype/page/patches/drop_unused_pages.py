import frappe


def execute() -> None:
	for name in ("desktop", "space"):
		frappe.delete_doc("Page", name)
