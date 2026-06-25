import frappe
from frappe.database.schema import add_column
from frappe.model.rename_doc import rename_doc


def _resolve_list_layout_table_conflict():
	"""Unblock rename when both tables exist from a failed/partial migration."""
	if not (frappe.db.table_exists("List Filter") and frappe.db.table_exists("List Layout")):
		return

	filter_rows = frappe.db.count("List Filter", distinct=False)
	layout_rows = frappe.db.count("List Layout", distinct=False)

	if layout_rows and not filter_rows:
		# Data is already in tabList Layout; swap so rename_doc can finish.
		frappe.db.rename_table("List Layout", "List Filter")
	elif not layout_rows:
		frappe.db.sql_ddl("drop table `tabList Layout`")
	else:
		# Both populated: keep original List Filter rows.
		frappe.db.sql_ddl("drop table `tabList Layout`")


def execute():
	"""Rename List Filter DocType to List Layout before model sync."""
	if not frappe.db.exists("DocType", "List Filter"):
		return

	_resolve_list_layout_table_conflict()

	if frappe.db.table_exists("List Filter") and not frappe.db.has_column("List Filter", "route_signature"):
		add_column("List Filter", "route_signature", "Small Text")

	# Model sync may have created List Layout DocType before rename completed.
	if frappe.db.exists("DocType", "List Layout"):
		if frappe.db.table_exists("List Filter") and not frappe.db.table_exists("List Layout"):
			frappe.db.rename_table("List Filter", "List Layout")
		frappe.delete_doc("DocType", "List Filter", force=True)
		return

	rename_doc("DocType", "List Filter", "List Layout", force=True)
