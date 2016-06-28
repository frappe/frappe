import frappe

def execute():
	frappe.rename_doc('DocType', 'Newsletter List', 'Email Group')
	frappe.rename_doc('DocType', 'Newsletter List Subscriber', 'Email Group Member')