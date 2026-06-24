# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import qb
from frappe.model.document import Document


class SyncedReportSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enable_synced_reports: DF.Check
		frequency: DF.Literal["Hourly", "Daily"]
	# end: auto-generated types

	_DOCTYPE_NAME = "Synced Report Doctype"

	def validate(self):
		old_doc = self.get_doc_before_save()
		if (old_doc.enable_synced_reports != self.enable_synced_reports) or (
			old_doc.frequency != self.frequency
		):
			synced_report_scheduler(self.enable_synced_reports, self.frequency)


def disable_cron_job():
	if event := frappe.db.get_all(
		"Scheduler Event", {"scheduled_against": "Synced Report Settings"}, pluck="name"
	):
		event = event[0]
		frappe.db.delete("Scheduled Job Type", {"scheduler_event": event})
		frappe.db.delete("Scheduler Event", event)


def enable_cron_job(frequency: str = "Daily"):
	cron_format = "0 0 * * *" if frequency == "Daily" else "0 * * * *"

	# schedule cron job
	event = frappe.get_doc(
		{
			"doctype": "Scheduler Event",
			"scheduled_against": "Synced Report Settings",
			"method": "frappe.core.doctype.synced_report_settings.synced_report_settings.start_sync",
		}
	).insert()
	frappe.get_doc(
		{
			"doctype": "Scheduled Job Type",
			"frequency": "Cron",
			"scheduler_event": event.name,
			"cron_format": cron_format,
			"method": "frappe.core.doctype.synced_report_settings.synced_report_settings.start_sync",
			"create_log": True,
		}
	).insert()


def synced_report_scheduler(enable: bool = False, frequency: str = "Daily"):
	# trash old job and recreate
	disable_cron_job()
	if enable:
		enable_cron_job(frequency)


def start_sync():
	_dt = qb.DocType("Doctype To Sync")
	to_sync = (
		qb.from_(_dt)
		.select(_dt.doc_type)
		.distinct()
		.where(_dt.parenttype.eq("Report") & _dt.parentfield.eq("doctype_to_sync"))
		.run(pluck="doc_type")
	)
	for x in to_sync:
		doc = frappe.get_doc(
			{
				"doctype": "DuckDB Sync",
				"doc_type": x,
			}
		).insert()
		doc.submit()
