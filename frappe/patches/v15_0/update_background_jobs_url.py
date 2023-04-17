import frappe


def execute():
	item = frappe.db.exists("Navbar Item", {"item_label": "Background Jobs"})
	if not item:
		return

	frappe.set_value("Navbar Item", item, "route", "/app/rq-job")
