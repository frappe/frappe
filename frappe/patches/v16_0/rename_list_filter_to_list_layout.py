import frappe
from frappe.database.schema import add_column
from frappe.model.rename_doc import rename_doc


def execute():
	"""Rename List Filter DocType to List Layout before model sync."""
	if not frappe.db.exists("DocType", "List Filter"):
		return

	# Handle partial migration state from failed reruns.
	if frappe.db.table_exists("List Filter") and frappe.db.table_exists("List Layout"):
		frappe.db.sql_ddl("drop table `tabList Layout`")

	if frappe.db.table_exists("List Filter") and not frappe.db.has_column("List Filter", "route_signature"):
		add_column("List Filter", "route_signature", "Small Text")

	rename_doc("DocType", "List Filter", "List Layout", force=True)
