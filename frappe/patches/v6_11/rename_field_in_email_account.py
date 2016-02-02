import frappe

def execute():
	frappe.reload_doc("email", "doctype", "email_account")
	frappe.db.sql("update `tabEmail Account` set email_server = pop3_server")
