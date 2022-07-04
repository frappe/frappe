# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from typing import TYPE_CHECKING

import frappe
from frappe.utils import convert_utc_to_user_timezone
from frappe.utils.background_jobs import get_queues, get_workers
from frappe.utils.scheduler import is_scheduler_inactive

if TYPE_CHECKING:
	from rq.job import Job

JOB_COLORS = {"queued": "orange", "failed": "red", "started": "blue", "finished": "green"}


@frappe.whitelist()
def get_info(view=None, queue_timeout=None, job_status=None) -> list[dict]:
	jobs = []

	def add_job(job: "Job", queue: str) -> None:

		if job.kwargs.get("site") == frappe.local.site:
			job_info = {
				"job_name": job.kwargs.get("kwargs", {}).get("playbook_method")
				or job.kwargs.get("kwargs", {}).get("job_type")
				or str(job.kwargs.get("job_name")),
				"status": job.get_status(),
				"queue": queue,
				"creation": convert_utc_to_user_timezone(job.created_at),
				"color": JOB_COLORS[job.get_status()],
			}

			if job.exc_info:
				job_info["exc_info"] = job.exc_info

			jobs.append(job_info)

	if view == "Jobs":
		queues = get_queues()
		for queue in queues:
			for job in queue.jobs:
				if job_status != "all" and job.get_status() != job_status:
					return
				if queue_timeout != "all" and not queue.name.endswith(f":{queue_timeout}"):
					return
				add_job(job, queue.name)

	elif view == "Workers":
		workers = get_workers()
		for worker in workers:
			current_job = worker.get_current_job()
			if current_job:
				if hasattr(current_job, "kwargs") and current_job.kwargs.get("site") == frappe.local.site:
					add_job(current_job, current_job.origin)
				else:
					jobs.append({"queue": worker.name, "job_name": "busy", "status": "", "creation": ""})
			else:
				jobs.append({"queue": worker.name, "job_name": "idle", "status": "", "creation": ""})

	return jobs


@frappe.whitelist()
def remove_failed_jobs():
	queues = get_queues()
	for queue in queues:
		fail_registry = queue.failed_job_registry
		for job_id in fail_registry.get_job_ids():
			job = queue.fetch_job(job_id)
			fail_registry.remove(job, delete_job=True)


@frappe.whitelist()
def get_scheduler_status():
	if is_scheduler_inactive():
		return {"status": "inactive"}
	return {"status": "active"}
