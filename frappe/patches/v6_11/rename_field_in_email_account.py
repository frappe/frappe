import frappe

def execute():
	frappe.reload_doctype("Email Account")
	frappe.db.sql("update `tabEmail Account` set email_server = pop3_server")
