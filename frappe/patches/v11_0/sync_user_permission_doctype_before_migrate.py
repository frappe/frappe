import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'user_permission')
	frappe.db.commit()