import frappe


def execute() -> None:
	frappe.reload_doctype("Letter Head")

	# source of all existing letter heads must be HTML
	frappe.db.sql("update `tabLetter Head` set source = 'HTML'")
