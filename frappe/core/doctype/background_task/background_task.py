# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt
import http
import traceback
from collections.abc import Callable
from typing import Any

from redis import Redis
from rq.command import send_stop_job_command
from rq.job import Callback, InvalidJobOperation, Job

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
		failure_callback: DF.Code | None
		kwargs: DF.Code | None
		method: DF.Data | None
		original_task: DF.Link | None
		queue: DF.Data | None
		result: DF.Code | None
		status: DF.Literal["Queued", "In Progress", "Completed", "Failed", "Stopped"]
		stopped_callback: DF.Code | None
		success_callback: DF.Code | None
		task_id: DF.Data
		timeout: DF.Int
		user: DF.Link | None
	# end: auto-generated types

	def stop(self):
		"""Stop the task"""
		try:
			send_stop_job_command(connection=get_redis_conn(), job_id=f"{frappe.local.site}::{self.task_id}")
		except InvalidJobOperation:
			frappe.msgprint(_("Job is not running."), title=_("Invalid Operation"))

	def retry(self) -> Job:
		"""Retry the task"""
		return enqueue(
			method=self.method,
			queue=self.queue,
			timeout=self.timeout,
			event=self.task_id,
			on_success=self.success_callback,
			on_failure=self.failure_callback,
			on_stopped=self.stopped_callback,
			at_front=bool(self.at_front),
			kwargs=frappe.parse_json(self.kwargs),
		)


@frappe.whitelist(methods=["POST"])
def enqueue_task(
	method: str,
	queue: str = "default",
	timeout: int | None = None,
	on_success: str | None = None,
	on_failure: str | None = None,
	on_stopped: str | None = None,
	at_front: bool = False,
	kwargs: dict | None = None,
	original_task: str | None = None,
):
	if kwargs is None:
		kwargs = {}

	# Ensure that the method to be queued exists
	try:
		frappe.get_attr(method)
	except ImportError:
		frappe.local.response["http_status_code"] = http.HTTPStatus.BAD_REQUEST
		return f"Method {method} not found"

	job = enqueue(
		method=method,
		queue=queue,
		timeout=timeout,
		on_success=on_success,
		on_failure=on_failure,
		on_stopped=on_stopped,
		at_front=at_front,
		original_task=original_task,
		**kwargs,
	)

	frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
	return {"task_id": job.id.split("::")[-1]}


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


@frappe.whitelist(methods=["POST"])
def retry_task(task_id: str):
	"""
	Method to retry a task

	:param task_id: The task's ID
	:return: The new task's ID
	"""
	task: BackgroundTask | None = frappe.get_doc("Background Task", {"task_id": task_id})
	if task:
		return task.retry()
	frappe.local.response["http_status_code"] = http.HTTPStatus.NOT_FOUND
	return "Task not found"


def enqueue(
	method: str | Callable,
	queue: str = "default",
	timeout: int | None = None,
	enqueue_after_commit: bool = False,
	on_success: Callable | str | None = None,
	on_failure: Callable | str | None = None,
	on_stopped: Callable | str | None = None,
	at_front: bool = False,
	original_task: str | None = None,
	**kwargs,
) -> Job | Any | None:
	"""
	Enqueue method to be executed using a background worker

	:param method: method string or method object
	:param queue: should be either long, default or short
	:param timeout: should be set according to the enqueued method's runtime
	:param enqueue_after_commit: if True, enqueue after the current transaction is committed
	:param on_success: Success callback
	:param on_failure: Failure callback
	:param on_stopped: Stopped callback
	:param at_front: Enqueue the job at the front of the queue or not
	:param kwargs: keyword arguments to be passed to the method
	:param original_task: Original task's name, if this is being re-tried
	:return: Job object normally, if executing now then the result of the method, nothing if enqueueing after commit
	"""

	from frappe.utils.background_jobs import (
		RQ_JOB_FAILURE_TTL,
		RQ_RESULTS_TTL,
		create_job_id,
		execute_job,
		get_queue,
		get_queues_timeout,
	)

	task_id = create_job_id()

	q = get_queue(queue)

	if not timeout:
		timeout = get_queues_timeout().get(queue) or 300

	meta = {"site": frappe.local.site}
	queue_args = meta | {
		"user": frappe.session.user,
		"method": method,
		"job_name": frappe.cstr(method),
		"kwargs": kwargs,
		"task_id": task_id,
	}

	def enqueue_call():
		return q.enqueue_call(
			execute_job,
			on_success=Callback(func=success_callback),
			on_failure=Callback(func=failure_callback),
			on_stopped=Callback(func=stopped_callback),
			timeout=timeout,
			meta=meta,
			kwargs=queue_args,
			at_front=at_front,
			failure_ttl=frappe.conf.get("rq_job_failure_ttl", RQ_JOB_FAILURE_TTL),
			result_ttl=frappe.conf.get("rq_results_ttl", RQ_RESULTS_TTL),
			job_id=task_id,
		)

	doc: BackgroundTask = frappe.new_doc(
		"Background Task",
		task_id=task_id.split("::")[-1],
		user=frappe.session.user,
		status="Queued",
		method=frappe.utils.method_to_string(method),
		queue=queue,
		timeout=timeout,
		kwargs=frappe.as_json(kwargs),
		at_front=at_front,
	)

	if on_success:
		doc.success_callback = frappe.utils.method_to_string(on_success)

	if on_failure:
		doc.failure_callback = frappe.utils.method_to_string(on_failure)

	if on_stopped:
		doc.stopped_callback = frappe.utils.method_to_string(on_stopped)

	if original_task:
		doc.original_task = original_task

	doc.insert(ignore_permissions=True)
	frappe.utils.notify_user(
		frappe.session.user,
		"Alert",
		frappe.session.user,
		"Background Task",
		doc.name,
		frappe._("Job queued:") + f" {doc.method}",
	)

	if enqueue_after_commit:
		frappe.db.after_commit.add(enqueue_call)
		return

	return enqueue_call()


def success_callback(job: Job, connection: Redis, result: Any) -> None:
	"""Callback function to update the status of the job to "Completed"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc("Background Task", {"task_id": task_id}, for_update=True)
	try:
		doc.status = "Completed"
		doc.result = result
		doc.save()

		if doc.success_callback:
			frappe.call(doc.success_callback, job, connection, result)

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
		frappe.db.set_value("Background Task", {"task_id": task_id}, "status", "Completed")
	frappe.db.commit()
	frappe.destroy()


def failure_callback(job: Job, connection: Redis, *exc_info) -> None:
	"""Callback function to update the status of the job to "Failed"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc("Background Task", {"task_id": task_id}, for_update=True)
	try:
		doc.status = "Failed"
		doc.result = "".join(traceback.format_exception(*exc_info))
		doc.save()

		if doc.failure_callback:
			frappe.call(doc.failure_callback, job, connection, *exc_info)
		else:
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
		frappe.db.set_value("Background Task", {"task_id": task_id}, "status", "Failed")
	frappe.db.commit()
	frappe.destroy()


def stopped_callback(job: Job, connection: Redis) -> None:
	"""Callback function to update the status of the job to "Stopped"."""
	frappe.init(site=job.meta["site"])
	frappe.connect()
	task_id = strip_site_from_task_id(job.id)
	doc = frappe.get_doc("Background Task", {"task_id": task_id}, for_update=True)
	try:
		doc.status = "Stopped"
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
		frappe.db.set_value("Background Task", {"task_id": task_id}, "status", "Stopped")
	frappe.db.commit()
	frappe.destroy()


def publish_task_progress(task_id: str, message: str, progress: float):
	"""
	Show the progress of a task

	:param task_id: Task ID
	"""
	frappe.publish_realtime(
		"background_task",
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
