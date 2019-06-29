import frappe

def execute():
	key = frappe.db.get_single_value("Google Maps Settings", "client_key")
	frappe.db.set_value("Google Settings", None, "api_key", key)
	frappe.db.commit()