# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from datetime import datetime
from typing import Dict, List

from croniter import croniter

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from frappe.utils.background_jobs import enqueue, get_jobs


class ScheduledJobType(Document):
	def autoname(self):
		self.name = ".".join(self.method.split(".")[-2:])

	def validate(self):
		if self.frequency != "All":
			# force logging for all events other than continuous ones (ALL)
			self.create_log = 1

	def enqueue(self, force=False):
		# enqueue event if last execution is done
		if self.is_event_due() or force:
			if frappe.flags.enqueued_jobs:
				frappe.flags.enqueued_jobs.append(self.method)

			if frappe.flags.execute_job:
				self.execute()
			else:
				if not self.is_job_in_queue():
					enqueue(
						"frappe.core.doctype.scheduled_job_type.scheduled_job_type.run_scheduled_job",
						queue=self.get_queue_name(),
						job_type=self.method,
					)
					return True

		return False

	def is_event_due(self, current_time=None):
		"""Return true if event is due based on time lapsed since last execution"""
		# if the next scheduled event is before NOW, then its due!
		return self.get_next_execution() <= (current_time or now_datetime())

	def is_job_in_queue(self):
		queued_jobs = get_jobs(site=frappe.local.site, key="job_type")[frappe.local.site]
		return self.method in queued_jobs

	def get_next_execution(self):
		CRON_MAP = {
			"Yearly": "0 0 1 1 *",
			"Annual": "0 0 1 1 *",
			"Monthly": "0 0 1 * *",
			"Monthly Long": "0 0 1 * *",
			"Weekly": "0 0 * * 0",
			"Weekly Long": "0 0 * * 0",
			"Daily": "0 0 * * *",
			"Daily Long": "0 0 * * *",
			"Hourly": "0 * * * *",
			"Hourly Long": "0 * * * *",
			"All": "0/" + str((frappe.get_conf().scheduler_interval or 240) // 60) + " * * * *",
		}

		if not self.cron_format:
			self.cron_format = CRON_MAP[self.frequency]

		return croniter(
			self.cron_format, get_datetime(self.last_execution or datetime(2000, 1, 1))
		).get_next(datetime)

	def execute(self):
		self.scheduler_log = None
		try:
			self.log_status("Start")
			if self.server_script:
				script_name = frappe.db.get_value("Server Script", self.server_script)
				if script_name:
					frappe.get_doc("Server Script", script_name).execute_scheduled_method()
			else:
				frappe.get_attr(self.method)()
			frappe.db.commit()
			self.log_status("Complete")
		except Exception:
			frappe.db.rollback()
			self.log_status("Failed")

	def log_status(self, status):
		# log file
		frappe.logger("scheduler").info(f"Scheduled Job {status}: {self.method} for {frappe.local.site}")
		self.update_scheduler_log(status)

	def update_scheduler_log(self, status):
		if not self.create_log:
			# self.get_next_execution will work properly iff self.last_execution is properly set
			if self.frequency == "All" and status == "Start":
				self.db_set("last_execution", now_datetime(), update_modified=False)
				frappe.db.commit()
			return
		if not self.scheduler_log:
			self.scheduler_log = frappe.get_doc(
				dict(doctype="Scheduled Job Log", scheduled_job_type=self.name)
			).insert(ignore_permissions=True)
		self.scheduler_log.db_set("status", status)
		if status == "Failed":
			self.scheduler_log.db_set("details", frappe.get_traceback())
		if status == "Start":
			self.db_set("last_execution", now_datetime(), update_modified=False)
		frappe.db.commit()

	def get_queue_name(self):
		return "long" if ("Long" in self.frequency) else "default"

	def on_trash(self):
		frappe.db.sql("delete from `tabScheduled Job Log` where scheduled_job_type=%s", self.name)


@frappe.whitelist()
def execute_event(doc: str):
	frappe.only_for("System Manager")
	doc = json.loads(doc)
	frappe.get_doc("Scheduled Job Type", doc.get("name")).enqueue(force=True)
	return doc


def run_scheduled_job(job_type: str):
	"""This is a wrapper function that runs a hooks.scheduler_events method"""
	try:
		frappe.get_doc("Scheduled Job Type", dict(method=job_type)).execute()
	except Exception:
		print(frappe.get_traceback())


def sync_jobs(hooks: Dict = None):
	frappe.reload_doc("core", "doctype", "scheduled_job_type")
	scheduler_events = hooks or frappe.get_hooks("scheduler_events")
	all_events = insert_events(scheduler_events)
	clear_events(all_events)


def insert_events(scheduler_events: Dict) -> List:
	cron_jobs, event_jobs = [], []
	for event_type in scheduler_events:
		events = scheduler_events.get(event_type)
		if isinstance(events, dict):
			cron_jobs += insert_cron_jobs(events)
		else:
			# hourly, daily etc
			event_jobs += insert_event_jobs(events, event_type)
	return cron_jobs + event_jobs


def insert_cron_jobs(events: Dict) -> List:
	cron_jobs = []
	for cron_format in events:
		for event in events.get(cron_format):
			cron_jobs.append(event)
			insert_single_event("Cron", event, cron_format)
	return cron_jobs


def insert_event_jobs(events: List, event_type: str) -> List:
	event_jobs = []
	for event in events:
		event_jobs.append(event)
		frequency = event_type.replace("_", " ").title()
		insert_single_event(frequency, event)
	return event_jobs


def insert_single_event(frequency: str, event: str, cron_format: str = None):
	cron_expr = {"cron_format": cron_format} if cron_format else {}
	doc = frappe.get_doc(
		{
			"doctype": "Scheduled Job Type",
			"method": event,
			"cron_format": cron_format,
			"frequency": frequency,
		}
	)

	if not frappe.db.exists(
		"Scheduled Job Type", {"method": event, "frequency": frequency, **cron_expr}
	):
		try:
			doc.insert()
		except frappe.DuplicateEntryError:
			doc.delete()
			doc.insert()


def clear_events(all_events: List):
	for event in frappe.get_all("Scheduled Job Type", fields=["name", "method", "server_script"]):
		is_server_script = event.server_script
		is_defined_in_hooks = event.method in all_events

		if not (is_defined_in_hooks or is_server_script):
			frappe.delete_doc("Scheduled Job Type", event.name)
