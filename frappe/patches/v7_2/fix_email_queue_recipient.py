import frappe

def execute():
	frappe.reload_doc('email', 'doctype', 'email_queue_recipient')
	frappe.db.sql('update `tabEmail Queue Recipient` set parenttype="recipients"')