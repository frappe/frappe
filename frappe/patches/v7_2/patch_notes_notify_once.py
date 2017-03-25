import frappe

def execute():
	frappe.reload_doctype('Note')
	frappe.db.sql('''
		update tabNote set
			notify_once = 1''')