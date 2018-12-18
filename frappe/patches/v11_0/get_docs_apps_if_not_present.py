import frappe
from frappe.utils.help import setup_apps_for_docs

def execute():
	for app in frappe.get_installed_apps():
		setup_apps_for_docs(app)
