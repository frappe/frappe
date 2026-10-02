import frappe


def execute():
	"""Keep Administrator password login working on existing sites."""
	frappe.db.set_single_value("System Settings", "disable_administrator_password_login", 0)
