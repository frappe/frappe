import frappe
from frappe.database.schema import add_column
from frappe.model.rename_doc import rename_doc
from frappe.patches.v16_0.rename_list_layout_filter_name_to_layout_name import (
	migrate_filter_name_to_layout_name,
)


def execute():
	"""Rename List Filter DocType to List Layout before model sync."""
	if not frappe.db.exists("DocType", "List Filter"):
		return

	if frappe.db.table_exists("List Filter") and not frappe.db.has_column("List Filter", "route_signature"):
		add_column("List Filter", "route_signature", "Data")

	rename_doc("DocType", "List Filter", "List Layout", force=True)
	migrate_filter_name_to_layout_name()
