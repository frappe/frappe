import frappe

def execute():
	frappe.reload_doctype("System Settings")
	# setting week_starts_on value as "Monday" to avoid breaking change
	# because before the configuration was introduced, system used to consider "Monday" as start of the week
	frappe.db.set_value("System Settings", "System Settings", "week_starts_on", "Monday")