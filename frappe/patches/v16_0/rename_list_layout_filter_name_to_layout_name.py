import frappe


def _list_layout_columns():
	"""Read tabList Layout columns without using cached metadata."""
	table = "tabList Layout"
	frappe.client_cache.delete_value(f"table_columns::{table}")
	frappe.cache.delete_value(f"table_columns::{table}")
	return set(frappe.db.get_db_table_columns(table))


def migrate_filter_name_to_layout_name():
	"""Rename filter_name to layout_name on tabList Layout (idempotent)."""
	if not frappe.db.table_exists("List Layout"):
		return

	columns = _list_layout_columns()
	has_filter_name = "filter_name" in columns
	has_layout_name = "layout_name" in columns

	if has_filter_name and not has_layout_name:
		frappe.db.rename_column("List Layout", "filter_name", "layout_name")
		return

	if has_filter_name and has_layout_name:
		# Model sync may have added an empty layout_name before this patch ran.
		table = frappe.qb.DocType("List Layout")
		(
			frappe.qb.update(table)
			.set(table.layout_name, table.filter_name)
			.where((table.filter_name != "") & ((table.layout_name == "") | table.layout_name.isnull()))
		).run()
		frappe.db.sql_ddl("ALTER TABLE `tabList Layout` DROP COLUMN `filter_name`")


def execute():
	"""Rename filter_name column to layout_name on List Layout."""
	migrate_filter_name_to_layout_name()
