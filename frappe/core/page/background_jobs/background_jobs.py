# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import json
from typing import TYPE_CHECKING, Dict, List

from rq import Queue, Worker

import frappe
from frappe import _
from frappe.utils import convert_utc_to_user_timezone, format_datetime
from frappe.utils.background_jobs import get_redis_conn
from frappe.utils.scheduler import is_scheduler_inactive

if TYPE_CHECKING:
	from rq.job import Job

JOB_COLORS = {"queued": "orange", "failed": "red", "started": "blue", "finished": "green"}


@frappe.whitelist()
def get_info(show_failed=False) -> List[Dict]:
	if isinstance(show_failed, str):
		show_failed = json.loads(show_failed)

	conn = get_redis_conn()
	queues = Queue.all(conn)
	workers = Worker.all(conn)
	jobs = []

	def add_job(job: "Job", name: str) -> None:
		if job.kwargs.get("site") == frappe.local.site:
			job_info = {
				"job_name": job.kwargs.get("kwargs", {}).get("playbook_method")
				or job.kwargs.get("kwargs", {}).get("job_type")
				or str(job.kwargs.get("job_name")),
				"status": job.get_status(),
				"queue": name,
				"creation": format_datetime(convert_utc_to_user_timezone(job.created_at)),
				"color": JOB_COLORS[job.get_status()],
			}

			if job.exc_info:
				job_info["exc_info"] = job.exc_info

			jobs.append(job_info)

	# show worker jobs
	for worker in workers:
		job = worker.get_current_job()
		if job:
			add_job(job, worker.name)

	for queue in queues:
		# show active queued jobs
		if queue.name != "failed":
			for job in queue.jobs:
				add_job(job, queue.name)

		# show failed jobs, if requested
		if show_failed:
			fail_registry = queue.failed_job_registry
			for job_id in fail_registry.get_job_ids():
				job = queue.fetch_job(job_id)
				if job:
					add_job(job, queue.name)

	return jobs


@frappe.whitelist()
def remove_failed_jobs():
	conn = get_redis_conn()
	queues = Queue.all(conn)
	for queue in queues:
		fail_registry = queue.failed_job_registry
		for job_id in fail_registry.get_job_ids():
			job = queue.fetch_job(job_id)
			fail_registry.remove(job, delete_job=True)


@frappe.whitelist()
def get_scheduler_status():
	if is_scheduler_inactive():
		return [_("Inactive"), "red"]
	return [_("Active"), "green"]
