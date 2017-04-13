import frappe

def execute():
	frappe.reload_doctype('Note')
	frappe.db.sql('''
		update tabNote set
			notify_on_every_login = 0''')
	