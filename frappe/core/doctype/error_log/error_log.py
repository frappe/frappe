# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Count, Date, Max, Min, Now
from frappe.utils.caching import http_cache


class ErrorLog(Document):
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

	def validate(self):
		self.method = str(self.method)
		self.error = str(self.error)

		if len(self.method) > 140:
			self.error = f"{self.method}\n{self.error}"
			self.method = self.method[:140]

	def onload(self):
		if not self.seen and not frappe.flags.read_only:
			self.db_set("seen", 1, update_modified=0)
			frappe.db.commit()

	@staticmethod
	def clear_old_logs(days=30):
		table = frappe.qb.DocType("Error Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
def clear_error_logs():
	"""Flush all Error Logs"""
	frappe.only_for("System Manager")
	frappe.db.truncate("Error Log")


@frappe.whitelist()
@http_cache(max_age=5 * 60)
def get_fingerprint_stats(fingerprint: str) -> dict:
	"""Aggregate occurrences of a given error fingerprint for the Sentry-like widget.

	Returns total count, first/last seen and a daily timeline over the retention window.
	"""
	frappe.has_permission("Error Log", throw=True)

	table = frappe.qb.DocType("Error Log")

	summary = (
		frappe.qb.from_(table)
		.where(table.fingerprint == fingerprint)
		.select(
			Count("*").as_("count"),
			Min(table.creation).as_("first_seen"),
			Max(table.creation).as_("last_seen"),
		)
	).run(as_dict=True)[0]

	timeline = (
		frappe.qb.from_(table)
		.where(table.fingerprint == fingerprint)
		.where(table.creation >= (Now() - Interval(days=30)))
		.groupby(Date(table.creation))
		.orderby(Date(table.creation))
		.select(Date(table.creation).as_("day"), Count("*").as_("count"))
	).run(as_dict=True)

	return {
		"count": summary.count or 0,
		"first_seen": summary.first_seen,
		"last_seen": summary.last_seen,
		"timeline": timeline,
	}
