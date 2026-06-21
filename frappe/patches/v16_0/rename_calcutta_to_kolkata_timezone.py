import frappe


def execute():
	frappe.db.set_value("User", {"time_zone": "Asia/Calcutta"}, "time_zone", "Asia/Kolkata")

	if frappe.db.get_single_value("System Settings", "time_zone") == "Asia/Calcutta":
		frappe.db.set_single_value("System Settings", "System Settings", "time_zone", "Asia/Kolkata")
