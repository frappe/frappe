import frappe

def execute():
	if frappe.db.has_column('DocField', 'in_filter'):
		frappe.db.sql('alter table tabDocField drop column in_filter')