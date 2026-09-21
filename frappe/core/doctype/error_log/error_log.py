# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.query_builder.functions import Count, Date, Max, Min
from frappe.utils import add_days, cint, now
from frappe.utils.caching import http_cache
from frappe.utils.logging import LogDocument, get_log_db, log_table, run_log_query


def _cutoff(days: int) -> str:
	"""Return the timestamp `days` in the past, as a string.

	The cutoff is computed in Python rather than with `Now() - Interval(days=...)`, which the
	query builder renders for SQLite as `CURRENT_TIMESTAMP - datetime('now', '+N days')` --
	one timestamp minus another, which SQLite evaluates numerically and never matches. A
	literal keeps the comparison correct, and `creation` is an ISO timestamp so string
	ordering is chronological ordering.
	"""
	return add_days(now(), -cint(days))


class ErrorLog(LogDocument):
	_DOCTYPE_NAME = "Error Log"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		error: DF.Code | None
		fingerprint: DF.Data | None
		metadata: DF.Code | None
		method: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.Data | None
		seen: DF.Check
		trace_id: DF.Data | None
	# end: auto-generated types

	# `frappe.model.virtual_doctype.validate_controller` compares each required method against
	# `controller.mro()[1]` -- here `LogDocument` -- so inheriting them reads as "not
	# overridden" and warns, even though they do override `Document`. Declaring them keeps the
	# check satisfied; the behaviour is entirely LogDocument's.
	#
	# The signatures mirror the parent's: `Document.insert` calls
	# `db_insert(ignore_if_duplicate=...)`, so narrowing these to `(self)` would raise
	# TypeError on every insert.

	def db_insert(self, *args, **kwargs):
		return super().db_insert(*args, **kwargs)

	def db_update(self, *args, **kwargs):
		return super().db_update(*args, **kwargs)

	def load_from_db(self):
		return super().load_from_db()

	def delete(self, *args, **kwargs):
		return super().delete(*args, **kwargs)

	def validate(self):
		self.method = str(self.method)
		self.error = str(self.error)

		if len(self.method) > 140:
			self.error = f"{self.method}\n{self.error}"
			self.method = self.method[:140]

	def onload(self):
		if not self.seen and not frappe.flags.read_only:
			# `LogDocument.db_set` writes to the log database and commits that connection, so
			# the previous explicit `frappe.db.commit()` -- which committed the *primary*
			# transaction -- is neither needed nor wanted here.
			self.db_set("seen", 1, update_modified=0)

	@staticmethod
	def clear_old_logs(days=30):
		qb, table = log_table("Error Log")
		run_log_query(qb.from_(table).where(table.creation < _cutoff(days)).delete())
		get_log_db().commit()


@frappe.whitelist()
def clear_error_logs():
	"""Flush all Error Logs"""
	frappe.only_for("System Manager")

	# `frappe.db.truncate` would target the primary database, where Error Log no longer has a
	# table. A DELETE on the log connection is the equivalent operation here.
	qb, table = log_table("Error Log")
	run_log_query(qb.from_(table).delete())
	get_log_db().commit()


@frappe.whitelist()
def get_queued_error_log_count() -> int:
	"""Return the number of Error Logs waiting for deferred insertion."""
	frappe.has_permission("Error Log", throw=True)

	from frappe.deferred_insert import queue_prefix

	return frappe.cache.llen(f"{queue_prefix}Error Log")


@frappe.whitelist()
def flush_error_logs():
	"""Insert all Error Logs currently waiting in the deferred insert queue."""
	frappe.only_for("System Manager")

	from frappe.deferred_insert import save_to_db

	save_to_db(doctype="Error Log")


@frappe.whitelist()
@http_cache(max_age=5 * 60)
def get_fingerprint_stats(fingerprint: str) -> dict:
	"""Aggregate occurrences of a given error fingerprint for the Sentry-like widget.

	Returns total count, first/last seen and a daily timeline over the retention window.
	"""
	frappe.has_permission("Error Log", throw=True)

	# Built with the log database's own dialect and run on its connection: `.run()` would
	# execute against `frappe.db`, which no longer holds these rows.
	qb, table = log_table("Error Log")

	summary = run_log_query(
		qb.from_(table)
		.where(table.fingerprint == fingerprint)
		.select(
			Count("*").as_("count"),
			Min(table.creation).as_("first_seen"),
			Max(table.creation).as_("last_seen"),
		),
		as_dict=True,
	)[0]

	timeline = run_log_query(
		qb.from_(table)
		.where(table.fingerprint == fingerprint)
		.where(table.creation >= _cutoff(30))
		.groupby(Date(table.creation))
		.orderby(Date(table.creation))
		.select(Date(table.creation).as_("day"), Count("*").as_("count")),
		as_dict=True,
	)

	return {
		"count": summary.count or 0,
		"first_seen": summary.first_seen,
		"last_seen": summary.last_seen,
		"timeline": timeline,
	}
