# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public background jobs API — tasks, RQ jobs, submissions and the scheduler.

Endpoints were consolidated from the Background Task, RQ Job, Submission
Queue and Scheduled Job Type doctypes and `frappe.utils.scheduler`; the old
dotted paths keep working via aliases in the original modules.
"""

from typing import TYPE_CHECKING

import frappe
from frappe.public_api import public

if TYPE_CHECKING:
	from frappe.model.document import Document

# ---------------------------------------------------------------------------
# Background Tasks (frappe.enqueue_task)
# ---------------------------------------------------------------------------


@public(group="Background Jobs")
@frappe.whitelist()
def get_recent_tasks(limit: int = 15) -> list[dict]:
	"""Return the most recent background tasks with live progress data.

	:param limit: number of tasks to return
	:return: The tasks, newest first, with cached progress/stage/status merged in.
	"""
	fields = [
		"name",
		"task_id",
		"task_name",
		"status",
		"stage",
		"progress",
		"show_progress_bar",
		"allow_user_cancellation",
		"allow_user_retry",
		"creation",
	]
	tasks = frappe.get_list("Background Task", fields=fields, limit=limit, order_by="creation desc")
	for task in tasks:
		cached = frappe.cache.get_value(f"background_task:{task.task_id}")
		if cached:
			if cached.get("progress") is not None:
				task["progress"] = cached["progress"]
			if cached.get("stage") is not None:
				task["stage"] = cached["stage"]
			if cached.get("status") is not None:
				task["status"] = cached["status"]
	return tasks


@public(group="Background Jobs")
@frappe.whitelist()
def get_cached_task_status(task_id: str) -> dict | None:
	"""Return the cached live status of a background task.

	:param task_id: task_id of the Background Task
	:return: The cached status data, or None if nothing is cached.
	"""
	return frappe.cache.get_value(f"background_task:{task_id}")


@public(group="Background Jobs")
@frappe.whitelist()
def stop_task(task_id: str) -> None:
	"""Cancel a queued or running background task.

	Allowed for the task's owner (if the task allows user cancellation) and
	System Managers.

	:param task_id: task_id of the Background Task
	"""
	task_name = frappe.db.get_value("Background Task", {"task_id": task_id}, "name")
	if not task_name:
		raise frappe.DoesNotExistError(frappe._("Background Task {0} not found").format(task_id))

	task = frappe.get_doc("Background Task", task_name)

	is_owner = task.user == frappe.session.user
	is_system_manager = "System Manager" in frappe.get_roles(frappe.session.user)
	if not (is_owner or is_system_manager):
		raise frappe.PermissionError(frappe._("Not permitted"))

	is_stoppable = task.status == "Queued" or (task.status == "Running" and task.allow_user_cancellation)
	if not is_stoppable and not is_system_manager:
		raise frappe.PermissionError(frappe._("Cancellation is not allowed for this task"))

	if task.status not in ("Queued", "Running"):
		raise frappe.InvalidStatusError(frappe._("Task is not queued or running"))

	from rq.command import send_stop_job_command
	from rq.job import Job, JobStatus

	from frappe.utils.background_jobs import create_job_id, get_redis_conn

	conn = get_redis_conn()
	rq_job_id = create_job_id(task.job_id or task.task_id)
	job = Job.fetch(rq_job_id, connection=conn)

	if job.get_status(refresh=True) == JobStatus.STARTED:
		send_stop_job_command(connection=conn, job_id=rq_job_id)
	else:
		job.cancel()

	task.db_set("status", "Cancelled")
	frappe.cache.delete_value(f"background_task:{task.task_id}")

	frappe.publish_realtime(
		event="task_update",
		message={"task_id": task.task_id, "status": "Cancelled", "task_name": task.task_name},
		user=task.user,
	)


@public(group="Background Jobs")
@frappe.whitelist()
def retry_task(task_id: str) -> None:
	"""Re-enqueue a failed or cancelled background task.

	Allowed for the task's owner (if the task allows user retry) and System
	Managers.

	:param task_id: task_id of the Background Task
	"""
	task_name = frappe.db.get_value("Background Task", {"task_id": task_id}, "name")
	if not task_name:
		raise frappe.DoesNotExistError(frappe._("Background Task {0} not found").format(task_id))

	task = frappe.get_doc("Background Task", task_name)

	is_owner = task.user == frappe.session.user
	is_system_manager = "System Manager" in frappe.get_roles(frappe.session.user)
	if not (is_owner or is_system_manager):
		raise frappe.PermissionError(frappe._("Not permitted"))

	if not task.allow_user_retry and not is_system_manager:
		raise frappe.PermissionError(frappe._("Retry is not allowed for this task"))

	if task.status not in ("Failed", "Cancelled"):
		raise frappe.InvalidStatusError(frappe._("Task can only be retried if failed or cancelled"))

	task.db_set(
		{
			"status": "Queued",
			"exception": None,
			"result": None,
			"progress": 0,
			"stage": None,
			"started_at": None,
			"ended_at": None,
		}
	)
	frappe.cache.delete_value(f"background_task:{task.task_id}")

	import json

	from frappe.utils.task_queue import _execute_task

	arguments = json.loads(task.arguments) if task.arguments else {}

	frappe.enqueue(
		_execute_task,
		queue=task.queue or "default",
		job_id=task.job_id or task.task_id,
		at_front=False,
		task_id=task.task_id,
		target_method=task.method,
		task_user=task.user,
		task_on_success=task.on_success_callback,
		task_on_failure=task.on_failure_callback,
		**arguments,
	)

	frappe.publish_realtime(
		event="task_update",
		message={"task_id": task.task_id, "status": "Queued", "task_name": task.task_name},
		user=task.user,
	)


# ---------------------------------------------------------------------------
# RQ jobs
# ---------------------------------------------------------------------------


@public(group="Background Jobs")
@frappe.whitelist()
def remove_failed_jobs() -> None:
	"""Delete all failed RQ jobs of the current site."""
	from rq.job import Job

	from frappe.core.doctype.rq_job.rq_job import filter_current_site_jobs
	from frappe.utils import create_batch
	from frappe.utils.background_jobs import get_queues, get_redis_conn

	frappe.only_for("System Manager")
	for queue in get_queues():
		fail_registry = queue.failed_job_registry
		failed_jobs = filter_current_site_jobs(fail_registry.get_job_ids(cleanup=False))

		# Delete in batches to avoid loading too many things in memory
		conn = get_redis_conn()
		for job_ids in create_batch(failed_jobs, 100):
			for job in Job.fetch_many(job_ids=job_ids, connection=conn):
				job and fail_registry.remove(job, delete_job=True)


@public(group="Background Jobs")
@frappe.whitelist()
def stop_job(job_id: str) -> None:
	"""Stop a queued or running RQ job.

	:param job_id: id of the RQ Job
	"""
	frappe.get_doc("RQ Job", job_id).stop_job()


@public(group="Background Jobs")
@frappe.whitelist()
def get_custom_queues() -> list[str]:
	"""Return the names of custom worker queues configured for this bench.

	:return: The configured queue names.
	"""
	frappe.has_permission("RQ Job", throw=True)
	return list((frappe.conf.workers or {}).keys())


# ---------------------------------------------------------------------------
# Submission queue
# ---------------------------------------------------------------------------


@public(group="Background Jobs")
@frappe.whitelist()
def get_latest_submissions(doctype: str, docname: str | int) -> dict | None:
	"""Return the latest queued submission of a document.

	:param doctype: DocType of the document
	:param docname: name of the document
	:return: Dict with the latest submission's name, exception and status, or
		None if the document was never queued.
	"""
	from frappe.core.doctype.submission_queue.submission_queue import format_tb

	# NOTE: not used creation as orderby intentianlly as we have used update_modified=False everywhere
	# hence assuming modified will be equal to creation for submission queue documents

	latest_submission = frappe.db.get_value(
		"Submission Queue",
		filters={"ref_doctype": doctype, "ref_docname": docname},
		fieldname=["name", "exception", "status"],
	)

	out = None
	if latest_submission:
		out = {
			"latest_submission": latest_submission[0],
			"exc": format_tb(latest_submission[1]),
			"status": latest_submission[2],
		}

	return out


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


@public(group="Background Jobs")
@frappe.whitelist()
def execute_event(doc: str | dict) -> dict:
	"""Run a scheduled job immediately.

	:param doc: the Scheduled Job Type document (or its dict/JSON); only `name` is used
	:return: The parsed doc, echoed back.
	"""
	frappe.only_for("System Manager")
	doc = frappe.parse_json(doc)
	frappe.get_doc("Scheduled Job Type", doc.get("name")).enqueue(force=True)
	return doc


@public(group="Background Jobs")
@frappe.whitelist()
def skip_next_execution(doc: str | dict) -> "Document":
	"""Skip the next scheduled run of a scheduled job.

	:param doc: the Scheduled Job Type document (or its dict/JSON); only `name` is used
	:return: The updated Scheduled Job Type document.
	"""
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType

	frappe.only_for("System Manager")
	doc = frappe.parse_json(doc)
	doc: ScheduledJobType = frappe.get_doc("Scheduled Job Type", doc.get("name"))
	doc.last_execution = doc.next_execution
	return doc.save()


@public(group="Background Jobs")
@frappe.whitelist()
def activate_scheduler() -> None:
	"""Re-enable and unpause the scheduler for this site."""
	from frappe.installer import update_site_config
	from frappe.utils.scheduler import enable_scheduler, is_scheduler_disabled

	frappe.only_for("Administrator")

	if frappe.local.conf.maintenance_mode:
		frappe.throw(frappe._("Scheduler can not be re-enabled when maintenance mode is active."))

	if is_scheduler_disabled():
		enable_scheduler()
	if frappe.conf.pause_scheduler:
		update_site_config("pause_scheduler", 0)


@public(group="Background Jobs")
@frappe.whitelist()
def get_scheduler_status() -> dict:
	"""Return whether the scheduler is active for this site.

	:return: Dict with `status` set to "active" or "inactive".
	"""
	from frappe.utils.scheduler import is_scheduler_inactive

	if is_scheduler_inactive():
		return {"status": "inactive"}
	return {"status": "active"}
