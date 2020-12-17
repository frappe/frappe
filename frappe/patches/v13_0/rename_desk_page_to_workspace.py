import frappe
from frappe.model.rename_doc import rename_doc

def execute():
	if frappe.db.exists("Doctype", "Desk Page"):
		rename_doc('DocType', 'Desk Page', 'Workspace')
		frappe.reload_doc('desk', 'doctype', 'workspace')
