# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import functools
import re

from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation, NoSuchJobError
from rq.job import Job
from rq.queue import Queue

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	cint,
	compare,
	convert_utc_to_system_timezone,
	create_batch,
	make_filter_dict,
)
from frappe.utils.background_jobs import get_queues, get_redis_conn

QUEUES = ["default", "long", "short"]
JOB_STATUSES = ["queued", "started", "failed", "finished", "deferred", "scheduled", "canceled"]

# Chunked-streaming bounds for the body-filter path.
#
# CHUNK_SIZE  — how many Job hashes we HGETALL in flight at a time. Peak
#               processing memory is roughly CHUNK_SIZE × avg job body size
#               (~500 × 2 KB ≈ 1 MB on a typical install). This decouples
#               memory safety from registry size: a registry of 100,000 jobs
#               still processes in 1 MB of peak hydrated state.
#
# MAX_FILTERED_JOBS — accumulator cap on the filtered result list. Past this
#               many matches we stop scanning and log. Pagination beyond the
#               cap is not meaningful — the user should narrow their filter.
#               At ~2 KB/job this is ~20 MB peak accumulated.
CHUNK_SIZE = 500
MAX_FILTERED_JOBS = 10000


def check_permissions(method):
	@functools.wraps(method)
	def wrapper(*args, **kwargs):
		frappe.only_for("System Manager")
		job = args[0].job
		if not for_current_site(job):
			raise frappe.PermissionError

		return method(*args, **kwargs)

	return wrapper


class RQJob(Document):
	_DOCTYPE_NAME = "RQ Job"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		arguments: DF.Code | None
		ended_at: DF.Datetime | None
		exc_info: DF.Code | None
		job_id: DF.Data | None
		job_name: DF.Data | None
		queue: DF.Literal["default", "short", "long"]
		started_at: DF.Datetime | None
		status: DF.Literal["queued", "started", "finished", "failed", "deferred", "scheduled", "canceled"]
		time_taken: DF.Duration | None
		timeout: DF.Duration | None
	# end: auto-generated types

	def load_from_db(self):
		try:
			job = Job.fetch(self.name, connection=get_redis_conn())
		except NoSuchJobError:
			raise frappe.DoesNotExistError

		if not for_current_site(job):
			raise frappe.PermissionError

		super(Document, self).__init__(serialize_job(job))
		self._job_obj = job

	@property
	def job(self):
		return self._job_obj

	@staticmethod
	def get_list(filters=None, start=0, page_length=20, order_by="creation desc"):
		filter_dict = make_filter_dict(filters or [])
		order_desc = "desc" in order_by
		if not RQJob._needs_body_filtering(filter_dict):
			matched_job_ids = RQJob.get_matching_job_ids(filters)
			page_ids = matched_job_ids[start : start + page_length]
			conn = get_redis_conn()
			jobs = [job for job in Job.fetch_many(job_ids=page_ids, connection=conn) if job]
			jobs.sort(key=lambda j: j.created_at, reverse=order_desc)
			return [serialize_job(job) for job in jobs]
		jobs = RQJob._get_all_jobs(filters)
		jobs.sort(key=lambda j: j.created_at, reverse=order_desc)
		return [serialize_job(job) for job in jobs[start : start + page_length]]

	@staticmethod
	def _needs_body_filtering(filters: dict) -> bool:
		BODY_FREE = {"queue", "status"}
		return any(key not in BODY_FREE for key in filters)

	@staticmethod
	def get_matching_job_ids(filters) -> list[str]:
		filters = make_filter_dict(filters or [])

		queues = _eval_filters(filters.get("queue"), QUEUES + get_custom_queues())
		statuses = _eval_filters(filters.get("status"), JOB_STATUSES)

		matched_job_ids = []
		for queue in get_queues():
			if not queue.name.endswith(tuple(queues)):
				continue
			for status in statuses:
				matched_job_ids.extend(fetch_job_ids(queue, status))

		return filter_current_site_jobs(matched_job_ids)

	@staticmethod
	def _get_all_jobs(filters=None) -> list[Job]:
		"""Hydrate every Job matching `filters`, applying every filter key.

		Chunked-streaming pipeline — peak processing memory stays at
		CHUNK_SIZE Job objects regardless of how many entries the registry
		contains. The full filtered set is accumulated (up to
		MAX_FILTERED_JOBS) so the caller can sort and paginate correctly,
		including across matches that live past the first few thousand IDs.

		  1. Fast-path: `name = <exact>` looks up Redis directly, skipping
		     the registry scan entirely (one HGETALL, no other I/O).
		  2. queue + status prefilter via `get_matching_job_ids` — cheap
		     LRANGE/ZRANGE on indexes, strings only.
		  3. Walk the candidate IDs in chunks of CHUNK_SIZE:
		       - bulk-hydrate the chunk (Job.fetch_many)
		       - apply remaining filters on the raw Job objects
		       - accumulate matches into the result list
		     Memory while scanning stays at one chunk's worth even when the
		     registry has 100,000+ IDs.
		  4. Stop and log if the accumulated match set hits
		     MAX_FILTERED_JOBS — past that, sort+paginate can't return
		     reliable pages anyway and the user should narrow their filter.

		`name` is intentionally NOT excluded from `remaining_filters` — the
		fast-path covers `name = X`; any other operator (`like`, `!=`, `in`)
		needs to route through matches_filters to be honored.
		"""
		filters = make_filter_dict(filters or [])

		# Stage 1: fast-path for exact-equality `name` filter.
		if name_filter := filters.get("name"):
			operator, operand = name_filter
			if operator == "=":
				try:
					job = Job.fetch(operand, connection=get_redis_conn())
					return [job] if for_current_site(job) else []
				except NoSuchJobError:
					return []

		# Stage 2: queue + status prefilter (string-only, cheap).
		matched_job_ids = RQJob.get_matching_job_ids(filters)

		exclude_filters = ("queue", "status")
		remaining_filters = {k: v for k, v in filters.items() if k not in exclude_filters}

		# Stage 3: walk candidates in chunks, accumulate filtered matches.
		conn = get_redis_conn()
		matched_jobs: list[Job] = []

		for i in range(0, len(matched_job_ids), CHUNK_SIZE):
			chunk_ids = matched_job_ids[i : i + CHUNK_SIZE]
			chunk_jobs = [job for job in Job.fetch_many(job_ids=chunk_ids, connection=conn) if job]

			if remaining_filters:
				chunk_jobs = [job for job in chunk_jobs if RQJob.matches_filters(job, remaining_filters)]

			matched_jobs.extend(chunk_jobs)

			# Stage 4: accumulator cap.
			if len(matched_jobs) >= MAX_FILTERED_JOBS:
				scanned = min(i + CHUNK_SIZE, len(matched_job_ids))
				frappe.log_error(
					title="RQ Job list view: results truncated",
					message=(
						f"Filter matched at least {MAX_FILTERED_JOBS} jobs after scanning "
						f"{scanned} of {len(matched_job_ids)} candidates. "
						f"Narrow your filter to see complete results."
					),
				)
				matched_jobs = matched_jobs[:MAX_FILTERED_JOBS]
				break

		return matched_jobs

	@staticmethod
	def matches_filters(job: Job, filters: dict) -> bool:
		for fieldname, filter_data in filters.items():
			operator, operand = filter_data

			if fieldname == "job_name":
				val = derive_job_name(job)
			elif fieldname == "name":
				val = job.id
			else:
				val = getattr(job, fieldname, job.kwargs.get(fieldname))

			if not compare(val, operator, operand):
				return False
		return True

	@check_permissions
	def delete(self):
		self.job.delete()

	@check_permissions
	def stop_job(self):
		try:
			send_stop_job_command(connection=get_redis_conn(), job_id=self.job_id)
		except InvalidJobOperation:
			frappe.msgprint(_("Job is not running."), title=_("Invalid Operation"))

	@check_permissions
	def cancel(self):
		if self.status == "queued":
			self.job.cancel()
		else:
			frappe.msgprint(
				_("Job is in {0} state and can't be cancelled").format(self.status),
				title=_("Invalid Operation"),
			)

	@staticmethod
	def get_count(filters=None) -> int:
		filter_dict = make_filter_dict(filters or [])
		if not RQJob._needs_body_filtering(filter_dict):
			return len(RQJob.get_matching_job_ids(filters))
		return len(RQJob._get_all_jobs(filters))

	# None of these methods apply to virtual job doctype, overriden for sanity.
	@staticmethod
	def get_stats():
		return {}

	def db_insert(self, *args, **kwargs):
		pass

	def db_update(self, *args, **kwargs):
		pass


def derive_job_name(job: Job) -> str:
	"""Compute the human-readable job name shown in the list view.

	Used by both serialize_job (for display) and matches_filters (for filtering)
	so the value a user types in the filter always matches the value they see.
	Handles two transformations the raw kwargs don't reflect:

	  1. `frappe.utils.background_jobs.run_doc_method` is rewritten to
	     `<doctype>.<doc_method>` (e.g. SalesInvoice.validate)
	  2. Jobs enqueued with a function object render as
	     `<function name at 0x...>` — strip to just the bare name
	"""
	job_kwargs = job.kwargs.get("kwargs", {})
	job_name = job_kwargs.get("job_type") or str(job.kwargs.get("job_name"))
	if job_name == "frappe.utils.background_jobs.run_doc_method":
		doctype = job_kwargs.get("doctype")
		doc_method = job_kwargs.get("doc_method")
		if doctype and doc_method:
			job_name = f"{doctype}.{doc_method}"

	if matches := re.match(r"<function (?P<func_name>.*) at 0x.*>", job_name):
		job_name = matches.group("func_name")

	return job_name


def serialize_job(job: Job) -> frappe._dict:
	modified = job.last_heartbeat or job.ended_at or job.started_at or job.created_at
	job_name = derive_job_name(job)

	exc_info = None

	# Get exc_string from the job result if it exists
	if job_result := job.latest_result():
		exc_info = job_result.exc_string

	return frappe._dict(
		name=job.id,
		job_id=job.id,
		queue=job.origin.rsplit(":", 1)[1],
		job_name=job_name,
		status=job.get_status(),
		started_at=convert_utc_to_system_timezone(job.started_at) if job.started_at else "",
		ended_at=convert_utc_to_system_timezone(job.ended_at) if job.ended_at else "",
		time_taken=(job.ended_at - job.started_at).total_seconds() if job.ended_at else "",
		exc_info=exc_info,
		arguments=frappe.as_json(job.kwargs),
		timeout=job.timeout,
		creation=convert_utc_to_system_timezone(job.created_at),
		modified=convert_utc_to_system_timezone(modified),
		_comment_count=0,
		owner=job.kwargs.get("user"),
		modified_by=job.kwargs.get("user"),
	)


def for_current_site(job: Job) -> bool:
	return job.kwargs.get("site") == frappe.local.site


def filter_current_site_jobs(job_ids: list[str]) -> list[str]:
	site = frappe.local.site

	return [j for j in job_ids if j.startswith(site)]


def _eval_filters(filter, values: list[str]) -> list[str]:
	if filter:
		operator, operand = filter
		return [val for val in values if compare(val, operator, operand)]
	return values


def fetch_job_ids(queue: Queue, status: str) -> list[str]:
	registry_map = {
		"queued": queue,  # self
		"started": queue.started_job_registry,
		"finished": queue.finished_job_registry,
		"failed": queue.failed_job_registry,
		"deferred": queue.deferred_job_registry,
		"scheduled": queue.scheduled_job_registry,
		"canceled": queue.canceled_job_registry,
	}

	registry = registry_map.get(status)
	if registry is not None:
		if isinstance(registry, Queue):
			job_ids = registry.get_job_ids()
		else:
			job_ids = registry.get_job_ids(cleanup=False)
		return [j for j in job_ids if j]

	return []


@frappe.whitelist()
def remove_failed_jobs():
	frappe.only_for("System Manager")
	for queue in get_queues():
		fail_registry = queue.failed_job_registry
		failed_jobs = filter_current_site_jobs(fail_registry.get_job_ids(cleanup=False))

		# Delete in batches to avoid loading too many things in memory
		conn = get_redis_conn()
		for job_ids in create_batch(failed_jobs, 100):
			for job in Job.fetch_many(job_ids=job_ids, connection=conn):
				job and fail_registry.remove(job, delete_job=True)


def get_all_queued_jobs():
	jobs = []
	for q in get_queues():
		jobs.extend(q.get_jobs())

	return [job for job in jobs if for_current_site(job)]


@frappe.whitelist()
def stop_job(job_id: str):
	frappe.get_doc("RQ Job", job_id).stop_job()


@frappe.whitelist()
def get_custom_queues():
	frappe.has_permission("RQ Job", throw=True)
	return list((frappe.conf.workers or {}).keys())
