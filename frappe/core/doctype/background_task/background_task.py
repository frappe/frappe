# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt
import http
import traceback
import uuid
from collections.abc import Callable
from typing import Any

from redis import Redis
from rq.command import send_stop_job_command
from rq.job import InvalidJobOperation, Job

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import get_redis_conn


class BackgroundTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		at_front: DF.Check
		kwargs: DF.Code | None
		method: DF.Data | None
		original_task: DF.Link | None
		queue: DF.Data | None
		result: DF.Code | None
		status: DF.Literal["Queued", "In Progress", "Completed", "Failed", "Stopped"]
		task_end: DF.Datetime | None
		task_id: DF.Data
		task_runtime: DF.Duration | None
		task_start: DF.Datetime | None
		timeout: DF.Int
		user: DF.Link | None
	# end: auto-generated types

	@property
	def task_runtime(self):
		return ((self.task_end or frappe.utils.now_datetime()) - self.task_start).total_seconds()

	def stop(self):
		"""Stop the task"""
		try:
			send_stop_job_command(connection=get_redis_conn(), job_id=f"{frappe.local.site}::{self.task_id}")
		except InvalidJobOperation:
			frappe.msgprint(_("Job is not running."), title=_("Invalid Operation"))


@frappe.whitelist(methods=["POST"])
def retry_task(
	queue: str = "default",
	timeout: int | None = None,
	at_front: bool = False,
	original_task: str | None = None,
):
	if task := frappe.get_doc("Background Task", original_task):
		job = enqueue(
			method=task.method,
			queue=queue,
			timeout=timeout,
			at_front=at_front,
			**task.kwargs,
		)

		frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
		return {"task_id": job.id.split("::")[-1]}
	frappe.local.response["http_status_code"] = http.HTTPStatus.NOT_FOUND
	return f"Task {original_task} not found"


@frappe.whitelist(methods=["POST"])
def stop_task(task_id: str):
	"""
	Method to stop a task

	:param task_id: Task ID
	"""
	task: BackgroundTask | None = frappe.get_doc("Background Task", {"task_id": task_id})
	if task:
		task.stop()
		return "Stopped task"
	frappe.local.response["http_status_code"] = http.HTTPStatus.NOT_FOUND
	return "Task not found"


def enqueue(
	method: str | Callable,
	queue: str = "default",
	timeout: int | None = None,
	enqueue_after_commit: bool = False,
	at_front: bool = False,
	original_task: str | None = None,
	**kwargs,
) -> Job | Any | None:
	"""
	Enqueue method to be executed using a background worker
	"""

	job_id = str(uuid.uuid4())

	doc: BackgroundTask = frappe.new_doc(
		"Background Task",
		task_id=job_id,
		user=frappe.session.user,
		status="Queued",
		method=frappe.utils.method_to_string(method),
		queue=queue,
		timeout=timeout,
		kwargs=frappe.as_json(kwargs),
		at_front=at_front,
		original_task=original_task,
	)
	doc.insert()

	from frappe.utils.background_jobs import enqueue as enqueue_job

	return enqueue_job(
		method=method,
		queue=queue,
		timeout=timeout,
		at_front=at_front,
		enqueue_after_commit=enqueue_after_commit,
		on_success=success_callback,
		on_failure=failure_callback,
		job_id=job_id,
		**kwargs,
	)


def success_callback(job: Job, connection: Redis, result: Any) -> None:
	"""Callback function to update the status of the job to "Completed"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc(
		"Background Task",
		task_id,
	)
	try:
		doc.status = "Completed"
		doc.result = result
		doc.task_end = frappe.utils.now_datetime()
		doc.save()

		frappe.utils.notify_user(
			frappe.session.user,
			"Alert",
			frappe.session.user,
			"Background Task",
			doc.name,
			frappe._("Job successfully completed:") + f" {doc.method}",
		)
	except Exception:
		frappe.db.rollback()
		doc.log_error("Error in success callback")
		frappe.db.set_value(
			"Background Task", task_id, {"status": "Completed", "task_end": frappe.utils.now_datetime()}
		)
	frappe.db.commit()
	frappe.destroy()


def failure_callback(job: Job, connection: Redis, *exc_info) -> None:
	"""Callback function to update the status of the job to "Failed"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc("Background Task", task_id)
	try:
		doc.status = "Failed"
		doc.result = "".join(traceback.format_exception(*exc_info))
		doc.task_end = frappe.utils.now()
		doc.save()

		from frappe.utils.background_jobs import truncate_failed_registry

		frappe.call(truncate_failed_registry, job, connection, *exc_info)

		frappe.utils.notify_user(
			frappe.session.user,
			"Alert",
			frappe.session.user,
			"Background Task",
			doc.name,
			frappe._("Job failed:") + f" {doc.method}",
		)
	except Exception:
		frappe.db.rollback()
		doc.log_error("Error in failure callback")
		frappe.db.set_value(
			"Background Task", task_id, {"status": "Failed", "task_end": frappe.utils.now_datetime()}
		)
	frappe.db.commit()
	frappe.destroy()


def stopped_callback(job: Job, connection: Redis) -> None:
	"""Callback function to update the status of the job to "Stopped"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc("Background Task", task_id)
	try:
		doc.status = "Stopped"
		doc.task_end = frappe.utils.now()
		doc.save()

		if doc.stopped_callback:
			frappe.call(doc.stopped_callback, job, connection)
		frappe.utils.notify_user(
			frappe.session.user,
			"Alert",
			frappe.session.user,
			"Background Task",
			doc.name,
			frappe._("Job stopped:") + f" {doc.method}",
		)
	except Exception:
		frappe.db.rollback()
		doc.log_error("Error in stopped callback")
		frappe.db.set_value(
			"Background Task",
			{"task_id": task_id},
			{"status": "Stopped", "task_end": frappe.utils.now_datetime()},
		)
	frappe.db.commit()
	frappe.destroy()


def publish_task_progress(task_id: str, message: str, progress: float):
	"""
	Show the progress of a task

	:param task_id: Task ID
	"""
	task = frappe.get_doc("Background Task", strip_site_from_task_id(task_id))
	frappe.publish_realtime(
		"background_task",
		user=task.user,
		message={
			"message": message,
			"progress": progress,
			"background_task_id": strip_site_from_task_id(task_id),
		},
	)


def strip_site_from_task_id(task_id: str) -> str:
	"""
	Task IDs are in the format `${site}::${task_id}`. This function strips the site from the task ID.

	:param task_id: The full task ID
	:return: The task ID without the site prefix
	"""
	return task_id.split("::")[-1]
