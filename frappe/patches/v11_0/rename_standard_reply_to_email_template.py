import frappe
from frappe.model.rename_doc import rename_doc


def execute() -> None:
	if frappe.db.table_exists("Standard Reply") and not frappe.db.table_exists("Email Template"):
		rename_doc("DocType", "Standard Reply", "Email Template")
		frappe.reload_doc("email", "doctype", "email_template")
