# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from rq.job import Job
from rq.queue import Queue

import frappe
from frappe.model.document import Document
from frappe.utils import (
	cint,
	compare,
	convert_utc_to_user_timezone,
	create_batch,
	make_filter_dict,
)
from frappe.utils.background_jobs import get_queues, get_redis_conn

QUEUES = ["default", "long", "short"]
JOB_STATUSES = ["queued", "started", "failed", "finished", "deferred", "scheduled", "canceled"]


class RQJob(Document):
	def load_from_db(self):
		job = Job.fetch(self.name, connection=get_redis_conn())
		super(Document, self).__init__(serialize_job(job))

	@staticmethod
	def get_list(args):

		start = cint(args.get("start"))
		page_length = cint(args.get("page_length"))

		order_desc = "desc" in args.get("order_by", "")

		matched_job_ids = RQJob.get_matching_job_ids(args)

		jobs = []
		for job_ids in create_batch(matched_job_ids, 100):
			jobs.extend(
				serialize_job(job)
				for job in Job.fetch_many(job_ids=job_ids, connection=get_redis_conn())
				if job and for_current_site(job)
			)
			if len(jobs) > start + page_length:
				# we have fetched enough. This is inefficient but because of site filtering TINA
				break

		return sorted(jobs, key=lambda j: j.modified, reverse=order_desc)[start : start + page_length]

	@staticmethod
	def get_matching_job_ids(args):
		filters = make_filter_dict(args.get("filters"))

		queues = _eval_filters(filters.get("queue"), QUEUES)
		statuses = _eval_filters(filters.get("status"), JOB_STATUSES)

		matched_job_ids = []
		for queue in get_queues():
			if not queue.name.endswith(tuple(queues)):
				continue
			for status in statuses:
				matched_job_ids.extend(fetch_job_ids(queue, status))

		return matched_job_ids

	@staticmethod
	def get_count(args) -> int:
		# Can not be implemented efficiently due to site filtering hence ignored.
		return 0

	# None of these methods apply to virtual job doctype, overriden for sanity.
	@staticmethod
	def get_stats(args):
		return {}

	def db_insert(self, *args, **kwargs):
		pass

	def db_update(self, *args, **kwargs):
		pass

	def delete(self):
		pass


def serialize_job(job: Job) -> frappe._dict:
	if not for_current_site(job):
		return frappe._dict()

	modified = job.last_heartbeat or job.ended_at or job.started_at or job.created_at

	return frappe._dict(
		name=job.id,
		job_id=job.id,
		queue=job.origin.rsplit(":", 1)[1],
		job_name=job.kwargs.get("kwargs", {}).get("job_type") or str(job.kwargs.get("job_name")),
		status=job.get_status(refresh=job.get_status() == "queued"),
		started_at=convert_utc_to_user_timezone(job.started_at) if job.started_at else "",
		ended_at=convert_utc_to_user_timezone(job.ended_at) if job.ended_at else "",
		time_taken=(job.ended_at - job.started_at).total_seconds() if job.ended_at else "",
		exc_info=job.exc_info,
		arguments=frappe.as_json(job.kwargs),
		timeout=job.timeout,
		creation=convert_utc_to_user_timezone(job.created_at),
		modified=convert_utc_to_user_timezone(modified),
		_comment_count=0,
	)


def for_current_site(job: Job) -> bool:
	return job.kwargs.get("site") == frappe.local.site


def _eval_filters(filter, values: list[str]) -> list[str]:
	if filter:
		operator, operand = filter
		return [val for val in values if compare(val, operator, operand)]
	return values


def fetch_job_ids(queue: Queue, status: str) -> list[str | None]:
	registry_map = {
		"queued": queue,  # self
		"started": queue.started_job_registry,
		"finished": queue.finished_job_registry,
		"failed": queue.failed_job_registry,
		"deferred": queue.deferred_job_registry,
		"scheduled": queue.scheduled_job_registry,
	}

	registry = registry_map.get(status)
	if registry:
		job_ids = registry.get_job_ids()
		return [j for j in job_ids if j]
	return []
