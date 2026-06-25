import frappe
from frappe.database.schema import add_column
from frappe.model.rename_doc import rename_doc

NEW_COLUMNS = [
	("route_signature", "Small Text"),
	("columns", "Long Text"),
	("sort_field", "Data"),
	("sort_order", "Data"),
]


def _table_row_count(table_name: str) -> int:
	return frappe.db.sql(f"select count(*) from `tab{table_name}`")[0][0]


def _ensure_columns(doctype: str):
	if not frappe.db.table_exists(doctype):
		return
	for column, fieldtype in NEW_COLUMNS:
		if not frappe.db.has_column(doctype, column):
			add_column(doctype, column, fieldtype)


def _rename_layout_name_column(doctype: str):
	if (
		frappe.db.table_exists(doctype)
		and frappe.db.has_column(doctype, "layout_name")
		and not frappe.db.has_column(doctype, "filter_name")
	):
		frappe.db.rename_column(doctype, "layout_name", "filter_name")


def execute():
	"""Revert List Layout to List Filter before model sync."""
	if not frappe.db.exists("DocType", "List Layout"):
		# Orphan table left by a failed forward migration.
		if frappe.db.table_exists("List Layout") and not _table_row_count("List Layout"):
			frappe.db.sql_ddl("drop table `tabList Layout`")
		if frappe.db.table_exists("List Filter"):
			_ensure_columns("List Filter")
			_rename_layout_name_column("List Filter")
		return

	# Both tables block rename — keep the one with data.
	if frappe.db.table_exists("List Filter") and frappe.db.table_exists("List Layout"):
		if _table_row_count("List Layout"):
			frappe.db.sql_ddl("drop table `tabList Filter`")
		else:
			frappe.db.sql_ddl("drop table `tabList Layout`")

	# Stale List Filter doctype left by model sync during a partial migration.
	if frappe.db.exists("DocType", "List Filter"):
		frappe.delete_doc("DocType", "List Filter", force=True)

	_ensure_columns("List Layout")
	_rename_layout_name_column("List Layout")
	rename_doc("DocType", "List Layout", "List Filter", force=True)
