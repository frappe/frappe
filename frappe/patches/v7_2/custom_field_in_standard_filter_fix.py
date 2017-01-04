import frappe

def execute():
	frappe.reload_doc('custom', 'doctype', 'custom_field', force=True)