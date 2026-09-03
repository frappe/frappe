import frappe
from frappe.desk.page.setup_wizard.setup_wizard import set_timezone


def execute():
	set_timezone(frappe.db.get_single_value("System Settings", "time_zone"))
