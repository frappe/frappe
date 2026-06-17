# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SyncedReportDoctype(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.synced_report_doctype_table.synced_report_doctype_table import (
			SyncedReportDoctypeTable,
		)
		from frappe.types import DF

		doctype_to_sync: DF.Table[SyncedReportDoctypeTable]
		enable_synced_reports: DF.Check
	# end: auto-generated types

	_DOCTYPE_NAME = "Synced Report Doctype"

	def validate(self):
		old_doc = self.get_doc_before_save()
		if old_doc.enable_synced_reports != self.enable_synced_reports:
			synced_report_scheduler(self.enable_synced_reports)


def synced_report_scheduler(enable: bool = False):
	if enable:
		# schedule cron job
		event = frappe.get_doc(
			{
				"doctype": "Scheduler Event",
				"scheduled_against": "Synced Report Doctype",
				"method": "frappe.core.doctype.synced_report_doctype.synced_report_doctype.start_sync",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Scheduled Job Type",
				"frequency": "Cron",
				"scheduler_event": event.name,
				"cron_format": "0 0 * * *",
				"method": "frappe.core.doctype.synced_report_doctype.synced_report_doctype.start_sync",
				"create_log": True,
			}
		).insert()
	else:
		# delete cron job
		if event := frappe.db.get_all(
			"Scheduler Event", {"scheduled_against": "Synced Report Doctype"}, pluck="name"
		):
			event = event[0]
			frappe.db.delete("Scheduled Job Type", {"scheduler_event": event})
			frappe.db.delete("Scheduler Event", event)


def start_sync():
	if frappe.get_single_value("Synced Report Doctype", "enable_synced_reports"):
		doctypes = set(
			frappe.db.get_all("Synced Report Doctype Table", fields=["doc_type"], pluck=["doc_type"])
		)
		for _dt in doctypes:
			doc = frappe.get_doc(
				{
					"doctype": "DuckDB Sync",
					"doc_type": _dt,
				}
			).insert()
			doc.submit()
