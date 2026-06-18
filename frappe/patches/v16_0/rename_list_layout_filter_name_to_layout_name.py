import frappe


def migrate_filter_name_to_layout_name():
	"""Rename filter_name to layout_name on tabList Layout (idempotent)."""
	if not frappe.db.table_exists("List Layout"):
		return

	has_filter_name = frappe.db.has_column("List Layout", "filter_name")
	has_layout_name = frappe.db.has_column("List Layout", "layout_name")

	if has_filter_name and not has_layout_name:
		frappe.db.rename_column("List Layout", "filter_name", "layout_name")
		return

	if has_filter_name and has_layout_name:
		# Model sync may have added an empty layout_name before this patch ran.
		frappe.db.sql(
			"""
			UPDATE `tabList Layout`
			SET layout_name = filter_name
			WHERE ifnull(filter_name, '') != '' AND ifnull(layout_name, '') = ''
			"""
		)
		if frappe.db.db_type == "mariadb":
			frappe.db.commit()
		frappe.db.sql_ddl("ALTER TABLE `tabList Layout` DROP COLUMN `filter_name`")


def execute():
	"""Rename filter_name column to layout_name on List Layout."""
	migrate_filter_name_to_layout_name()
