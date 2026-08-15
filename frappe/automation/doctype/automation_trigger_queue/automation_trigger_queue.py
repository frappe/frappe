# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.queue import QUEUE, WAITING_STATES
from frappe.model.document import Document

TABLE = f"tab{QUEUE}"
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

	MariaDB gets a generated column carrying the key plus a unique index on it, because it has
	no partial indexes. Postgres and SQLite express the rule directly as a partial unique index
	and skip the column: neither can index a virtual column, and CONCAT_WS is not immutable
	enough for a Postgres generated one.
	"""
	if frappe.db.db_type == "mariadb":
		_ensure_dedup_column()
		if not frappe.db.has_index(TABLE, DEDUP_INDEX):
			frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` ADD UNIQUE INDEX `{DEDUP_INDEX}` (`dedup_key`)")
	else:
		_ensure_partial_dedup_index()

	# Claim scan: the drainer's ORDER BY triggered_at over due waiting rows.
	frappe.db.add_index(QUEUE, ["status", "run_after", "triggered_at"], "drain_scan")

	# Enqueue lookup: _pending_row resolves (automation, ref_doctype, ref_name) before every
	# insert, and neither unique index can serve it - MariaDB's is on a column the query never
	# names, and a partial index is only usable when the planner can match its predicate.
	# Without this, queuing N documents against one flow costs O(N^2).
	frappe.db.add_index(QUEUE, ["automation", "ref_doctype", "ref_name"], LOOKUP_INDEX)


def _waiting_states_sql() -> str:
	return ", ".join(frappe.db.escape(state) for state in WAITING_STATES)


def _ensure_partial_dedup_index():
	# Raw DDL throughout: the query builder does not create indexes or generated columns.
	frappe.db.sql_ddl(f"DROP INDEX IF EXISTS `{DEDUP_INDEX}`")
	frappe.db.sql_ddl(
		f"""
		CREATE UNIQUE INDEX `{DEDUP_INDEX}` ON `{TABLE}` (`automation`, `ref_doctype`, `ref_name`)
		WHERE `status` IN ({_waiting_states_sql()}) AND `resume_run` IS NULL
		"""
	)


def _ensure_dedup_column():
	"""Rebuild the generated column whenever its CASE no longer matches WAITING_STATES."""
	# Raw SQL: information_schema is not a DocType.
	expression = frappe.db.sql(
		"""
		SELECT GENERATION_EXPRESSION FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'dedup_key'
		""",
		TABLE,
	)
	if expression and all(state in (expression[0][0] or "") for state in WAITING_STATES):
		return
	_rebuild_dedup_column()


def _rebuild_dedup_column():
	if frappe.db.has_index(TABLE, DEDUP_INDEX):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` DROP INDEX `{DEDUP_INDEX}`")
	if frappe.db.has_column(QUEUE, "dedup_key"):
		frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` DROP COLUMN `dedup_key`")
		# Raw DDL leaves the cached column list stale, and the re-add below reads it.
		frappe.client_cache.delete_value(f"table_columns::{TABLE}")
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
