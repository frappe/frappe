import frappe


def execute():
	frappe.db.delete("DocType", {"name": "Feedback Request"})
