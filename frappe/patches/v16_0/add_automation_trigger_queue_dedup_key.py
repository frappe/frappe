# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe

TABLE = "tabAutomation Trigger Queue"


def execute():
	"""Add the dedup_key generated column (JSON can't express it) + its unique index and the
	drain-scan index. dedup_key is NULL for non-Pending and resume rows, so — NULLs being
	distinct in a unique index — only concurrent Pending triggers for the same ref collide."""
	if not frappe.db.table_exists("Automation Trigger Queue"):
		return

	if not frappe.db.has_column("Automation Trigger Queue", "dedup_key"):
		frappe.db.sql_ddl(
			f"""
			ALTER TABLE `{TABLE}`
			ADD COLUMN `dedup_key` VARCHAR(420)
			AS (
				CASE WHEN `status` = 'Pending' AND `resume_run` IS NULL
				THEN CONCAT_WS(':', `automation`, `ref_doctype`, `ref_name`) END
			) VIRTUAL
			"""
		)

	if not frappe.db.has_index(TABLE, "unique_dedup_key"):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` ADD UNIQUE INDEX `unique_dedup_key` (`dedup_key`)")

	if not frappe.db.has_index(TABLE, "drain_scan"):
		frappe.db.sql_ddl(
			f"ALTER TABLE `{TABLE}` ADD INDEX `drain_scan` (`status`, `run_after`, `triggered_at`)"
		)
