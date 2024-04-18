# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt
"""
Basic system health check report to see how everything on site is functioning in one single page.

Metrics:
- [x] Background jobs, workers and scheduler summary, queue stats
- [x] SocketIO works (using basic ping test)
- [x] Email queue flush and pull
- [x] Error logs status
- [x] Database - storage usage and top tables, version
- [x] Cache
- [x] Storage - files usage
- [ ] Backups
- [ ] Log cleanup status
- [ ] User - new users, sessions stats, failed login attempts
- [ ] Updates / Security updates ?




"""

import os
from collections import defaultdict

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import get_queue, get_queue_list
from frappe.utils.data import add_to_date
from frappe.utils.scheduler import get_scheduler_status


class SystemHealthReport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.system_health_db_table.system_health_db_table import SystemHealthDBTable
		from frappe.desk.doctype.system_health_queue.system_health_queue import SystemHealthQueue
		from frappe.desk.doctype.system_health_workers.system_health_workers import SystemHealthWorkers
		from frappe.types import DF

		background_workers: DF.Table[SystemHealthWorkers]
		backups_size: DF.Float
		binary_logging: DF.Data | None
		bufferpool_size: DF.Data | None
		cache_keys: DF.Int
		cache_memory_usage: DF.Data | None
		database: DF.Data | None
		database_version: DF.Data | None
		db_storage_usage: DF.Float
		failed_emails: DF.Int
		handled_emails: DF.Int
		onsite_backups: DF.Int
		pending_emails: DF.Int
		private_files_size: DF.Float
		public_files_size: DF.Float
		queue_status: DF.Table[SystemHealthQueue]
		scheduler_status: DF.Data | None
		socketio_ping_check: DF.Literal["Fail", "Pass"]
		socketio_transport_mode: DF.Literal["Polling", "Websocket"]
		top_db_tables: DF.Table[SystemHealthDBTable]
		top_errors: DF.Code | None
		total_background_workers: DF.Int
		total_errors: DF.Int
		total_outgoing_emails: DF.Int
		unhandled_emails: DF.Int
	# end: auto-generated types

	def db_insert(self, *args, **kwargs):
		raise NotImplementedError

	def load_from_db(self):
		super(Document, self).__init__({})
		self.fetch_background_workers()
		self.fetch_email_stats()
		self.fetch_errors()
		self.fetch_database_details()
		self.fetch_cache_details()
		self.fetch_storage_details()

	def fetch_background_workers(self):
		self.scheduler_status = get_scheduler_status().get("status")
		workers = frappe.get_all("RQ Worker")
		self.total_background_workers = len(workers)
		queue_summary = defaultdict(list)

		for worker in workers:
			queue_summary[worker.queue_type].append(worker)

		for queue_type, workers in queue_summary.items():
			self.append(
				"background_workers",
				{
					"count": len(workers),
					"queues": queue_type,
					"failed_jobs": sum(w.failed_job_count for w in workers),
					"utilization": sum(w.utilization_percent for w in workers) / len(workers),
				},
			)

		for queue in get_queue_list():
			q = get_queue(queue)
			self.append(
				"queue_status",
				{
					"queue": queue,
					"pending_jobs": q.count,
				},
			)

	def fetch_email_stats(self):
		threshold = add_to_date(None, days=-7, as_datetime=True)
		filters = {"creation": (">", threshold), "modified": (">", threshold)}
		self.total_outgoing_emails = frappe.db.count("Email Queue", filters)
		self.pending_emails = frappe.db.count("Email Queue", {"status": "Not Sent", **filters})
		self.failed_emails = frappe.db.count("Email Queue", {"status": "Error", **filters})
		self.unhandled_emails = frappe.db.count("Unhandled Email", filters)
		self.handled_emails = frappe.db.count(
			"Communication",
			{"sent_or_received": "Received", "communication_type": "Communication", **filters},
		)

	def fetch_errors(self):
		from terminaltables import AsciiTable

		threshold = add_to_date(None, days=-1, as_datetime=True)
		filters = {"creation": (">", threshold), "modified": (">", threshold)}
		self.total_errors = frappe.db.count("Error Log", filters)

		top_errors = frappe.db.sql(
			"""select method, count(*) as occurance
			from `tabError Log`
			where modified > %(threshold)s and creation > %(threshold)s
			group by method
			order by occurance desc
			limit 5""",
			{"threshold": threshold},
			as_list=True,
		)
		if top_errors:
			self.top_errors = AsciiTable([["Error Title", "Count"], *top_errors]).table

	def fetch_database_details(self):
		from frappe.core.report.database_storage_usage_by_tables.database_storage_usage_by_tables import (
			execute as db_report,
		)

		_cols, data = db_report()
		self.database = frappe.db.db_type
		self.db_storage_usage = sum(table.size for table in data)
		for row in data[:5]:
			self.append("top_db_tables", row)
		self.database_version = frappe.db.sql("select version()")[0][0]

		if frappe.db.db_type == "mariadb":
			self.bufferpool_size = frappe.db.sql("show variables like 'innodb_buffer_pool_size'")[0][1]
			self.binary_logging = frappe.db.sql("show variables like 'log_bin'")[0][1]

	def fetch_cache_details(self):
		self.cache_keys = len(frappe.cache.get_keys(""))
		self.cache_memory_usage = frappe.cache.execute_command("INFO", "MEMORY").get("used_memory_human")

	@classmethod
	def get_directory_size(cls, *path):
		folder = os.path.abspath(frappe.get_site_path(*path))
		# Copied as is from agent
		total_size = os.path.getsize(folder)
		for item in os.listdir(folder):
			itempath = os.path.join(folder, item)

			if not os.path.islink(itempath):
				if os.path.isfile(itempath):
					total_size += os.path.getsize(itempath)
				elif os.path.isdir(itempath):
					total_size += cls.get_directory_size(itempath)
		return total_size / (1024 * 1024)

	def fetch_storage_details(self):
		from frappe.desk.page.backups.backups import get_context

		self.backups_size = self.get_directory_size("private", "backups")
		self.private_files_size = self.get_directory_size("private", "files")
		self.public_files_size = self.get_directory_size("public", "files")
		self.onsite_backups = len(get_context({}).get("files", []))

	def db_update(self):
		raise NotImplementedError

	def delete(self):
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs):
		raise NotImplementedError

	@staticmethod
	def get_count(filters=None, **kwargs):
		raise NotImplementedError

	@staticmethod
	def get_stats(**kwargs):
		raise NotImplementedError
