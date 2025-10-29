# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import datetime
from contextlib import suppress

from rq import Worker

import frappe
from frappe.model.document import Document
from frappe.utils import cint, convert_utc_to_system_timezone
from frappe.utils.background_jobs import get_workers


class RQWorker(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		birth_date: DF.Datetime | None
		current_job_id: DF.Link | None
		failed_job_count: DF.Int
		last_heartbeat: DF.Datetime | None
		pid: DF.Data | None
		queue: DF.Data | None
		queue_type: DF.Literal["default", "long", "short"]
		status: DF.Data | None
		successful_job_count: DF.Int
		total_working_time: DF.Duration | None
		utilization_percent: DF.Percent
		worker_name: DF.Data | None
	# end: auto-generated types

	def load_from_db(self):
		all_workers = get_workers()
		workers = [w for w in all_workers if w.name == self.name]
		if not workers:
			raise frappe.DoesNotExistError
		d = serialize_worker(workers[0])

		super(Document, self).__init__(d)

	@staticmethod
	def get_list(start=0, page_length=0):
		workers = get_workers()

		valid_workers = [w for w in workers if w.pid]

		if page_length:
			valid_workers = valid_workers[start : start + page_length]
		else:
			valid_workers = valid_workers[start:]

		return [serialize_worker(worker) for worker in valid_workers]

	@staticmethod
	def get_count() -> int:
		return len(get_workers())

	# None of these methods apply to virtual workers, overriden for sanity.
	@staticmethod
	def get_stats():
		return {}

	def db_insert(self, *args, **kwargs):
		pass

	def db_update(self, *args, **kwargs):
		pass

	def delete(self):
		pass


def serialize_worker(worker: Worker) -> frappe._dict:
	queue_names = worker.queue_names()

	queue = ", ".join(queue_names)
	queue_types = ",".join(q.rsplit(":", 1)[1] for q in queue_names)

	current_job = worker.get_current_job_id()
	if current_job and not current_job.startswith(frappe.local.site):
		current_job = None

	return frappe._dict(
		name=worker.name,
		queue=queue,
		queue_type=queue_types,
		worker_name=worker.name,
		status=worker.get_state(),
		pid=worker.pid,
		current_job_id=current_job,
		last_heartbeat=convert_utc_to_system_timezone(worker.last_heartbeat),
		birth_date=convert_utc_to_system_timezone(worker.birth_date),
		successful_job_count=worker.successful_job_count,
		failed_job_count=worker.failed_job_count,
		total_working_time=worker.total_working_time,
		_comment_count=0,
		modified=convert_utc_to_system_timezone(worker.last_heartbeat),
		creation=convert_utc_to_system_timezone(worker.birth_date),
		utilization_percent=compute_utilization(worker),
	)


def compute_utilization(worker: Worker) -> float:
	with suppress(Exception):
		total_time = (
			datetime.datetime.now(datetime.timezone.utc)
			- worker.birth_date.replace(tzinfo=datetime.timezone.utc)
		).total_seconds()
		return worker.total_working_time / total_time * 100
