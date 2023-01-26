import frappe
from frappe.desk.page.setup_wizard.install_fixtures import update_global_search_doctypes


def execute():
	frappe.reload_doc("desk", "doctype", "global_search_doctype")
	frappe.reload_doc("desk", "doctype", "global_search_settings")
	update_global_search_doctypes()
