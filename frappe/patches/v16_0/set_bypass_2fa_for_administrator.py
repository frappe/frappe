import frappe


def execute():
	frappe.db.set_single_value("System Settings", "bypass_two_factor_auth_for_administrator", 1)
