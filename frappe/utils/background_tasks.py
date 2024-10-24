from collections.abc import Callable
from typing import Any

from rq.job import Job

import frappe


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

	:param method: method string or method object
	:param queue: should be either long, default or short
	:param timeout: should be set according to the enqueued method's runtime
	:param enqueue_after_commit: if True, enqueue after the current transaction is committed
	:param at_front: Enqueue the job at the front of the queue or not
	:param kwargs: keyword arguments to be passed to the method
	:param original_task: Original task's name, if this is being re-tried
	:return: Job object normally, if executing now then the result of the method, nothing if enqueueing after commit
	"""
	from frappe.core.doctype.background_task.background_task import enqueue

	return enqueue(
		method=method,
		queue=queue,
		timeout=timeout,
		enqueue_after_commit=enqueue_after_commit,
		at_front=at_front,
		original_task=original_task,
		**kwargs,
	)


def publish_task_progress(message: str, progress: float):
	"""
	Publish task progress to the user
	:param message: Message for the user
	:return: Nothing
	"""
	from frappe.core.doctype.background_task.background_task import publish_task_progress

	if frappe.job and frappe.job.task_id:
		publish_task_progress(frappe.job.task_id, message, progress)
	else:
		print(f"Task progress: {message=}, {progress=}")
