import frappe


def execute() -> None:
	days = frappe.db.get_single_value("Website Settings", "auto_account_deletion")
	frappe.db.set_single_value("Website Settings", "auto_account_deletion", days * 24)
