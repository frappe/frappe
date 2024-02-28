# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt
import traceback
from collections.abc import Callable
from typing import Any

from redis import Redis
from rq.job import Callback, Job

import frappe
from frappe.model.document import Document


class BackgroundTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		failure_callback: DF.Code | None
		method: DF.Data | None
		result: DF.Code | None
		status: DF.Literal["Queued", "In Progress", "Completed", "Failed", "Stopped"]
		stopped_callback: DF.Code | None
		success_callback: DF.Code | None
		task_id: DF.Data
		user: DF.Link | None
	# end: auto-generated types

	pass


def enqueue(
	method: str | Callable,
	queue: str = "default",
	timeout: int | None = None,
	event: str | None = None,
	enqueue_after_commit: bool = False,
	on_success: Callable | str | None = None,
	on_failure: Callable | str | None = None,
	on_stopped: Callable | str | None = None,
	at_front: bool = False,
	**kwargs,
) -> Job | Any | None:
	"""
	Enqueue method to be executed using a background worker

	:param method: method string or method object
	:param queue: should be either long, default or short
	:param timeout: should be set according to the functions
	:param event: this is passed to enable clearing of jobs from queues
	:param enqueue_after_commit: if True, enqueue after the current transaction is committed
	:param on_success: Success callback
	:param on_failure: Failure callback
	:param on_stopped: Stopped callback
	:param at_front: Enqueue the job at the front of the queue or not
	:param kwargs: keyword arguments to be passed to the method
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

	try:
		q = get_queue(queue)
	except ConnectionError:
		if frappe.local.flags.in_migrate:
			# If redis is not available during migration, execute the job directly
			print(f"Redis queue is unreachable: Executing {method} synchronously")
			return frappe.call(method, **kwargs)
		raise

	if not timeout:
		timeout = get_queues_timeout().get(queue) or 300

	queue_args = {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"method": method,
		"event": event,
		"job_name": frappe.cstr(method),
		"kwargs": kwargs,
	}

	def enqueue_call():
		return q.enqueue_call(
			execute_job,
			on_success=Callback(func=success_callback),
			on_failure=Callback(func=failure_callback),
			on_stopped=Callback(func=stopped_callback),
			timeout=timeout,
			kwargs=queue_args,
			at_front=at_front,
			failure_ttl=frappe.conf.get("rq_job_failure_ttl", RQ_JOB_FAILURE_TTL),
			result_ttl=frappe.conf.get("rq_results_ttl", RQ_RESULTS_TTL),
			job_id=task_id,
		)

	doc = frappe.new_doc(
		"Background Task",
		task_id=task_id.split("::")[-1],
		user=frappe.session.user,
		status="Queued",
		method=frappe.utils.method_to_string(method),
	)
	if on_success:
		doc.success_callback = frappe.utils.method_to_string(on_success)

	if on_failure:
		doc.failure_callback = frappe.utils.method_to_string(on_failure)

	if on_stopped:
		doc.stopped_callback = frappe.utils.method_to_string(on_stopped)

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
	frappe.init(site=job._kwargs.get("site"))
	frappe.connect()
	doc = frappe.get_doc("Background Task", {"task_id": job.id.split("::")[-1]}, for_update=True)
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
	frappe.db.commit()
	frappe.destroy()


def failure_callback(job: Job, connection: Redis, *exc_info) -> None:
	"""Callback function to update the status of the job to "Failed"."""
	frappe.init(site=job._kwargs.get("site"))
	frappe.connect()
	doc = frappe.get_doc("Background Task", {"task_id": job.id.split("::")[-1]}, for_update=True)
	doc.status = "Failed"
	doc.result = "".join(traceback.format_exception(*exc_info))
	doc.save()
	from frappe.utils.background_jobs import truncate_failed_registry

	if doc.failure_callback:
		frappe.call(doc.failure_callback, job, connection, *exc_info)
	else:
		frappe.call(truncate_failed_registry, job, connection, *exc_info)
	if failure_callback := job._kwargs.get("on_failure", truncate_failed_registry):
		failure_callback(job, connection, *exc_info)
	frappe.utils.notify_user(
		frappe.session.user,
		"Alert",
		frappe.session.user,
		"Background Task",
		doc.name,
		frappe._("Job failed:") + f" {doc.method}",
	)
	frappe.db.commit()
	frappe.destroy()


def stopped_callback(job: Job, connection: Redis, *args, **kwargs) -> None:
	"""Callback function to update the status of the job to "Stopped"."""
	frappe.init(site=job._kwargs.get("site"))
	frappe.connect()
	print("Stopped with args", args)
	print("Stopped with kwargs", kwargs)
	doc = frappe.get_doc("Background Task", {"task_id": job.id.split("::")[-1]}, for_update=True)
	doc.status = "Stopped"
	doc.save()
	if doc.stopped_callback:
		frappe.call(doc.stopped_callback, job, connection, *args, **kwargs)
	frappe.utils.notify_user(
		frappe.session.user,
		"Alert",
		frappe.session.user,
		"Background Task",
		doc.name,
		frappe._("Job stopped:") + f" {doc.method}",
	)
	frappe.db.commit()
	frappe.destroy()
