import frappe

def execute():
	if frappe.db.has_column('DocType', 'in_dialog'):
		frappe.db.sql('alter table tabDocType drop column in_dialog')