import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	"""Rename List Filter DocType to List Layout before model sync."""
	if frappe.db.exists("DocType", "List Layout"):
		return

	if not frappe.db.exists("DocType", "List Filter"):
		return

	if frappe.db.table_exists("tabList Filter") and not frappe.db.has_column(
		"List Filter", "route_signature"
	):
		frappe.db.add_column("List Filter", "route_signature", "Data")

	rename_doc("DocType", "List Filter", "List Layout", force=True)
