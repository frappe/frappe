import frappe
from frappe.desk.page.setup_wizard.install_fixtures import update_global_search_doctypes

def execute():
	update_global_search_doctypes()