import frappe
from frappe.desk.page.setup_wizard.setup_wizard import fill_required_system_settings


def execute():
	"""Sites set up without a region, like Frappe Cloud v2 sites, were left without a language and
	a time zone, so System Settings could no longer be saved."""
	if frappe.is_setup_complete():
		fill_required_system_settings()
