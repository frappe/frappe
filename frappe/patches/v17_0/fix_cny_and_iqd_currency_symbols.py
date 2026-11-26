import frappe


def execute():
	frappe.db.set_value("Currency", {"name": "CNY", "symbol": ("is", "not set")}, "symbol", "¥")
	frappe.db.set_value("Currency", {"name": "IQD", "symbol": "ع.د"}, "symbol", "د.ع")
