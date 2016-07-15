import frappe

def execute():
	frappe.rename_doc('DocType', 'Bulk Email', 'Email Queue')