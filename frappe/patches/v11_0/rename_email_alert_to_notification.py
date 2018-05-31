import frappe
from frappe.model.rename_doc import rename_doc

def execute():
	if frappe.db.table_exists("Email Alert") and not frappe.db.table_exists("Notification"):
		rename_doc('DocType', 'Email Alert', 'Notification')
		frappe.reload_doc('email', 'doctype', 'notification')
