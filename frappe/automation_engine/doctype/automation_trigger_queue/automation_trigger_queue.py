# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document

TABLE = "tabAutomation Trigger Queue"


class AutomationTriggerQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attempt: DF.Int
		automation: DF.Link
		depth: DF.Int
		event_payload: DF.JSON | None
		ref_doctype: DF.Data | None
		ref_name: DF.Data | None
		resume_from_idx: DF.Int
		resume_run: DF.Data | None
		run_after: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Done", "Failed", "Skipped"]
		triggered_at: DF.Datetime | None
	# end: auto-generated types

	pass


def on_doctype_update():
	ensure_dedup_indexes()


def ensure_dedup_indexes():
	if not frappe.db.has_column("Automation Trigger Queue", "dedup_key"):
		_add_dedup_column()
	if not frappe.db.has_index(TABLE, "unique_dedup_key"):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` ADD UNIQUE INDEX `unique_dedup_key` (`dedup_key`)")
	if not frappe.db.has_index(TABLE, "drain_scan"):
		frappe.db.sql_ddl(
			f"ALTER TABLE `{TABLE}` ADD INDEX `drain_scan` (`status`, `run_after`, `triggered_at`)"
		)


def _add_dedup_column():
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
