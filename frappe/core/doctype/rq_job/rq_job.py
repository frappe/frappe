# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import functools
import json
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
from frappe.utils.caching import request_cache

QUEUES = ["default", "long", "short"]
JOB_STATUSES = ["queued", "started", "failed", "finished", "deferred", "scheduled", "canceled"]

# HGETALL pipeline batch size — bounds peak in-flight memory (~1 MB at 500).
CHUNK_SIZE = 500

# Accumulator cap on body-filter matches; past this, scans truncate and log.
MAX_FILTERED_JOBS = 10000

# Per-(queue, status) cap for the pre-sort candidate set. Bounds cost at scale:
# 500k total jobs still process ≤ 21k IDs. Score-DESC per registry is a close
# proxy for created_at-DESC; pathological jobs may sample out. get_count on
# the cheap path uses uncapped enumeration for accurate totals.
CAP_PER_REGISTRY = 1000


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
		order_desc = "desc" in order_by.lower()

		if not RQJob._needs_body_filtering(filter_dict):
			# Cheap path: pre-sorted IDs → slice → hydrate only the visible page.
			matched_job_ids = _created_at_sorted_candidate_ids(filter_dict, desc=order_desc)
			page_ids = matched_job_ids[start : start + page_length]
			conn = get_redis_conn()
			jobs = [job for job in Job.fetch_many(job_ids=page_ids, connection=conn) if job]
			return [serialize_job(job) for job in jobs]

		# Body-filter path: pre-sort is exact, so limit = start + page_length suffices.
		jobs = RQJob._get_all_jobs(filters, limit=start + page_length, desc=order_desc)
		return [serialize_job(job) for job in jobs[start : start + page_length]]

	@staticmethod
	def _needs_body_filtering(filters: dict) -> bool:
		BODY_FREE = {"queue", "status"}
		return any(key not in BODY_FREE for key in filters)

	@staticmethod
	def get_matching_job_ids(filters) -> list[str]:
		"""Unsorted current-site IDs matching the queue/status filter.
		Used for counting; `get_list` uses the sorted variant for display."""
		return _enumerate_matching_job_ids(make_filter_dict(filters or []))

	@staticmethod
	def _get_all_jobs(filters=None, limit: int | None = None, desc: bool = True) -> list[Job]:
		"""Normalize filters and delegate to the cached impl. Same
		(filters, limit, desc) within a request reuses the cached scan."""
		filter_dict = make_filter_dict(filters or [])
		return _get_all_jobs_impl(frappe.as_json(filter_dict), limit, desc)

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


def _registry_for_status(queue: Queue, status: str):
	"""Return the RQ registry for `status` on `queue`, or None. `queued`
	is the Queue itself (LIST); other statuses are ZSET attributes."""
	return {
		"queued": queue,
		"started": queue.started_job_registry,
		"finished": queue.finished_job_registry,
		"failed": queue.failed_job_registry,
		"deferred": queue.deferred_job_registry,
		"scheduled": queue.scheduled_job_registry,
		"canceled": queue.canceled_job_registry,
	}.get(status)


def fetch_job_ids(queue: Queue, status: str) -> list[str]:
	registry = _registry_for_status(queue, status)
	if registry is None:
		return []

	if isinstance(registry, Queue):
		job_ids = registry.get_job_ids()
	else:
		job_ids = registry.get_job_ids(cleanup=False)
	return [j for j in job_ids if j]


def _fetch_recent_job_ids(queue: Queue, status: str, cap: int) -> list[str]:
	"""Top `cap` IDs from (queue, status) — score-DESC for ZSETs, tail-reversed
	for the queued LIST. Bounds the pre-sort candidate set at scale."""
	registry = _registry_for_status(queue, status)
	if registry is None:
		return []

	conn = registry.connection
	if isinstance(registry, Queue):
		raw = conn.lrange(registry.key, -cap, -1)
		return [(j.decode() if isinstance(j, bytes) else j) for j in reversed(raw) if j]

	raw = conn.zrange(registry.key, 0, cap - 1, desc=True)
	return [(j.decode() if isinstance(j, bytes) else j) for j in raw if j]


def _enumerate_matching_job_ids(filters: dict, cap: int | None = None) -> list[str]:
	"""Current-site candidate IDs from matching (queue, status) structures.

	`cap` bounds each (queue, status) contribution to the top-K by score
	(for the sort path). Uncapped returns the full set (for accurate counts).
	Order is registry concat, not sorted by created_at.

	Queue-name match uses `endswith` — see `notes/bug_list.md` (Bug 3) for
	the latent suffix-collision risk. Fixing that bug means updating just
	this one site.
	"""
	queue_names = _eval_filters(filters.get("queue"), QUEUES + get_custom_queues())
	statuses = _eval_filters(filters.get("status"), JOB_STATUSES)

	matched: list[str] = []
	for queue in get_queues():
		if not queue.name.endswith(tuple(queue_names)):
			continue
		for status in statuses:
			if cap is not None:
				matched.extend(_fetch_recent_job_ids(queue, status, cap))
			else:
				matched.extend(fetch_job_ids(queue, status))

	return filter_current_site_jobs(matched)


def _created_at_sorted_candidate_ids(filters: dict, desc: bool = True) -> list[str]:
	"""Current-site candidate IDs sorted by exact `created_at`.

	RQ's per-status ZSETs are scored by state-change time (finished_at + ttl,
	etc.), not by created_at, so score order ≠ created_at order in general.
	Instead: enumerate top-K per registry (see CAP_PER_REGISTRY), then pipeline
	one `HGET created_at` per candidate for exact sort. Orphan IDs (registry
	entry exists but hash was TTL-swept) drop out.
	"""
	candidate_ids = _enumerate_matching_job_ids(filters, cap=CAP_PER_REGISTRY)
	if not candidate_ids:
		return []

	conn = get_redis_conn()
	with conn.pipeline() as pipe:
		for job_id in candidate_ids:
			pipe.hget(f"rq:job:{job_id}", "created_at")
		created_ats = pipe.execute()

	# ISO 8601 strings sort correctly as strings — no parsing needed.
	dated = [
		(created_at.decode() if isinstance(created_at, bytes) else created_at, job_id)
		for job_id, created_at in zip(candidate_ids, created_ats, strict=True)
		if created_at
	]
	dated.sort(reverse=desc)
	return [job_id for _, job_id in dated]


@request_cache
def _get_all_jobs_impl(filter_key: str, limit: int | None, desc: bool) -> list[Job]:
	"""Hydrate matching Jobs — the actual body-filter scan.

	`filter_key` is `frappe.as_json(filter_dict)` — dicts aren't hashable for
	the `@request_cache` key. Same (filter_key, limit, desc) in a request
	reuses the cached result.

	Pipeline: exact-`name` fast-path via Job.fetch → pre-sort candidates by
	created_at → prefilter by `name` operator in Python (job.id == candidate
	id, no hydration needed) → chunked HGETALL + `matches_filters` for other
	body predicates → early-exit at `limit` or MAX_FILTERED_JOBS.
	"""
	# JSON round-trip turns tuple values into lists; downstream code expects tuples.
	filters = {k: tuple(v) for k, v in json.loads(filter_key).items()}

	# Fast-path: `name = <exact>` — one HGETALL, no scan.
	if name_filter := filters.get("name"):
		operator, operand = name_filter
		if operator == "=":
			try:
				job = Job.fetch(operand, connection=get_redis_conn())
				return [job] if for_current_site(job) else []
			except NoSuchJobError:
				return []

	matched_job_ids = _created_at_sorted_candidate_ids(filters, desc=desc)
	remaining_filters = {k: v for k, v in filters.items() if k not in ("queue", "status")}

	# ID prefilter: job.id == candidate id, so filter without hydrating.
	if name_filter := remaining_filters.pop("name", None):
		operator, operand = name_filter
		matched_job_ids = [j for j in matched_job_ids if compare(j, operator, operand)]

	conn = get_redis_conn()
	matched_jobs: list[Job] = []

	for i in range(0, len(matched_job_ids), CHUNK_SIZE):
		chunk_ids = matched_job_ids[i : i + CHUNK_SIZE]
		chunk_jobs = [job for job in Job.fetch_many(job_ids=chunk_ids, connection=conn) if job]

		if remaining_filters:
			chunk_jobs = [job for job in chunk_jobs if RQJob.matches_filters(job, remaining_filters)]

		matched_jobs.extend(chunk_jobs)

		if limit is not None and len(matched_jobs) >= limit:
			return matched_jobs[:limit]

		if len(matched_jobs) >= MAX_FILTERED_JOBS:
			# Pagination past the cap isn't meaningful — user should narrow filter.
			scanned = min(i + CHUNK_SIZE, len(matched_job_ids))
			frappe.log_error(
				title="RQ Job list view: results truncated",
				message=(
					f"Filter matched at least {MAX_FILTERED_JOBS} jobs after scanning "
					f"{scanned} of {len(matched_job_ids)} candidates. "
					f"Narrow your filter to see complete results."
				),
			)
			return matched_jobs[:MAX_FILTERED_JOBS]

	return matched_jobs


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
