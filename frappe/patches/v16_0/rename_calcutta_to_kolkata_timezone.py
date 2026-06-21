import frappe


def execute():
	frappe.db.set_value("User", {"time_zone": "Asia/Calcutta"}, "time_zone", "Asia/Kolkata")
