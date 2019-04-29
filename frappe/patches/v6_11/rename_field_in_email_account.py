from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("email", "doctype", "email_account")
	if frappe.db.has_column('Email Account', 'pop3_server'):
		frappe.db.sql("update `tabEmail Account` set email_server = pop3_server")
