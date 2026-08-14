# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine import WAITING_STATES
from frappe.model.document import Document

DOCTYPE = "Automation Trigger Queue"
TABLE = "tabAutomation Trigger Queue"
DEDUP_INDEX = "unique_dedup_key"
LOOKUP_INDEX = "pending_lookup"


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
		status: DF.Literal["Pending", "Scheduled", "Running", "Done", "Failed", "Skipped"]
		triggered_at: DF.Datetime | None
		triggered_by: DF.Link | None
	# end: auto-generated types

	pass


def on_doctype_update():
	ensure_dedup_indexes()


def ensure_dedup_indexes():
	"""Enforce "one waiting row per (automation, document)" in the database.

	MariaDB gets a generated column carrying the dedup key plus a unique index on it, because
	it has no partial indexes. Postgres and SQLite express the same rule directly as a partial
	unique index, and skip the column entirely - neither can index a virtual column, and
	CONCAT_WS is not immutable enough for a Postgres generated one.
	"""
	if frappe.db.db_type == "mariadb":
		_ensure_dedup_column()
		if not frappe.db.has_index(TABLE, DEDUP_INDEX):
			frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` ADD UNIQUE INDEX `{DEDUP_INDEX}` (`dedup_key`)")
	else:
		_ensure_partial_dedup_index()

	# Claim scan: the drainer's ORDER BY triggered_at over due waiting rows.
	frappe.db.add_index(DOCTYPE, ["status", "run_after", "triggered_at"], "drain_scan")

	# Enqueue lookup: _pending_row resolves (automation, ref_doctype, ref_name) before every
	# insert, and neither dedup index can serve it. MariaDB's is on the generated `dedup_key`
	# column, which the query never names; the partial one elsewhere is only usable when the
	# planner can match its predicate. Without this the lookup is a full table scan, so
	# queuing N documents against one flow costs O(N^2) and a bulk schedule never finishes.
	frappe.db.add_index(DOCTYPE, ["automation", "ref_doctype", "ref_name"], LOOKUP_INDEX)


def _waiting_states_sql() -> str:
	"""The WAITING_STATES tuple as a SQL list, so the constant stays the single source."""
	return ", ".join(frappe.db.escape(state) for state in WAITING_STATES)


def _ensure_partial_dedup_index():
	"""Rebuild the partial unique index every time rather than probing its stored predicate.

	Dropping and recreating is cheap on a table the purge sweep keeps short, and it is the
	only db-agnostic way to guarantee the predicate still matches WAITING_STATES.
	"""
	frappe.db.sql_ddl(f"DROP INDEX IF EXISTS `{DEDUP_INDEX}`")
	frappe.db.sql_ddl(
		f"""
		CREATE UNIQUE INDEX `{DEDUP_INDEX}` ON `{TABLE}` (`automation`, `ref_doctype`, `ref_name`)
		WHERE `status` IN ({_waiting_states_sql()}) AND `resume_run` IS NULL
		"""
	)


def _ensure_dedup_column():
	"""Rebuild the generated column whenever its CASE no longer matches WAITING_STATES."""
	if _dedup_column_is_current():
		return
	_drop_dedup_column()
	_add_dedup_column()


def _dedup_column_is_current() -> bool:
	expression = frappe.db.sql(
		"""
		SELECT GENERATION_EXPRESSION FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'dedup_key'
		""",
		TABLE,
	)
	if not expression:
		return False
	return all(state in (expression[0][0] or "") for state in WAITING_STATES)


def _drop_dedup_column():
	if frappe.db.has_index(TABLE, DEDUP_INDEX):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` DROP INDEX `{DEDUP_INDEX}`")
	if frappe.db.has_column("Automation Trigger Queue", "dedup_key"):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` DROP COLUMN `dedup_key`")
		# Raw DDL leaves the cached column list stale, and the re-add reads it.
		frappe.client_cache.delete_value(f"table_columns::{TABLE}")


def _add_dedup_column():
	frappe.db.sql_ddl(
		f"""
		ALTER TABLE `{TABLE}`
		ADD COLUMN `dedup_key` VARCHAR(420)
		AS (
			CASE WHEN `status` IN ({_waiting_states_sql()}) AND `resume_run` IS NULL
			THEN CONCAT_WS(':', `automation`, `ref_doctype`, `ref_name`) END
		) VIRTUAL
		"""
	)
