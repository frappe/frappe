import frappe


def execute() -> None:
	frappe.db.delete("DocType", {"name": "Feedback Request"})
