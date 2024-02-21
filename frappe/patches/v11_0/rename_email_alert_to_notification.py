import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	if frappe.db.table_exists("Email Alert Recipient") and not frappe.db.table_exists(
		"Notification Recipient"
	):
		rename_doc("DocType", "Email Alert Recipient", "Notification Recipient")
		frappe.reload_doc("email", "doctype", "notification_recipient")

	if frappe.db.table_exists("Email Alert") and not frappe.db.table_exists("Notification"):
		rename_doc("DocType", "Email Alert", "Notification")
		frappe.reload_doc("email", "doctype", "notification")
