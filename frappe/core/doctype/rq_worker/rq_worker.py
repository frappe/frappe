# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import datetime
from contextlib import suppress

from rq import Worker

import frappe
from frappe.model.document import Document
from frappe.utils import cint, convert_utc_to_user_timezone
from frappe.utils.background_jobs import get_workers


class RQWorker(Document):
	def load_from_db(self):

		all_workers = get_workers()
		worker = [w for w in all_workers if w.pid == cint(self.name)][0]
		d = serialize_worker(worker)

		super(Document, self).__init__(d)

	@staticmethod
	def get_list(args):
		start = cint(args.get("start")) or 0
		page_length = cint(args.get("page_length")) or 20

		workers = get_workers()

		valid_workers = [w for w in workers if w.pid][start : start + page_length]
		return [serialize_worker(worker) for worker in valid_workers]

	@staticmethod
	def get_count(args) -> int:
		return len(get_workers())

	# None of these methods apply to virtual workers, overriden for sanity.
	@staticmethod
	def get_stats(args):
		return {}

	def db_insert(self, *args, **kwargs):
		pass

	def db_update(self, *args, **kwargs):
		pass

	def delete(self):
		pass


def serialize_worker(worker: Worker) -> frappe._dict:
	queue = ", ".join(worker.queue_names())

	return frappe._dict(
		name=worker.pid,
		queue=queue,
		queue_type=queue.rsplit(":", 1)[1],
		worker_name=worker.name,
		status=worker.get_state(),
		pid=worker.pid,
		current_job_id=worker.get_current_job_id(),
		last_heartbeat=convert_utc_to_user_timezone(worker.last_heartbeat),
		birth_date=convert_utc_to_user_timezone(worker.birth_date),
		successful_job_count=worker.successful_job_count,
		failed_job_count=worker.failed_job_count,
		total_working_time=worker.total_working_time,
		_comment_count=0,
		modified=convert_utc_to_user_timezone(worker.last_heartbeat),
		creation=convert_utc_to_user_timezone(worker.birth_date),
		utilization_percent=compute_utilization(worker),
	)


def compute_utilization(worker: Worker) -> float:
	with suppress(Exception):
		total_time = (datetime.datetime.utcnow() - worker.birth_date).total_seconds()
		return worker.total_working_time / total_time * 100
