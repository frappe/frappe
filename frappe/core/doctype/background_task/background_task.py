# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import time
from collections.abc import Callable

import frappe
from frappe.model.document import Document

PUBLISH_THROTTLE_SECONDS = 0.2


class BackgroundTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		arguments: DF.JSON | None
		ended_at: DF.Datetime | None
		on_failure_callback: DF.Data | None
		on_success_callback: DF.Data | None
		exception: DF.LongText | None
		method: DF.Data
		progress: DF.Percent
		queue: DF.Data | None
		ref_docname: DF.DynamicLink | None
		ref_doctype: DF.Link | None
		result: DF.LongText | None
		show_progress_bar: DF.Check
		stage: DF.Data | None
		started_at: DF.Datetime | None
		status: DF.Literal["Queued", "Running", "Completed", "Failed", "Cancelled"]
		task_id: DF.Data
		job_id: DF.Data | None
		task_name: DF.Data
		user: DF.Link
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._last_published: float = 0.0

	def after_insert(self):
		frappe.publish_realtime(
			event="task_update",
			message={"task_id": self.task_id, "task_name": self.task_name, "status": "Queued"},
			user=self.user,
			after_commit=True,
		)

	def update_stage(self, stage: str) -> None:
		"""Publish a stage description without numeric progress"""
		self._publish({"task_id": self.task_id, "task_name": self.task_name, "stage": stage})

	def publish_progress(self, percent: int | float, stage: str | None = None) -> None:
		"""Publish numeric progress (0-100)"""
		now = time.monotonic()
		if percent < 100 and (now - self._last_published) < PUBLISH_THROTTLE_SECONDS:
			return
		self._last_published = now

		message: dict = {"task_id": self.task_id, "task_name": self.task_name, "progress": percent}
		if stage:
			message["stage"] = stage
		self._publish(message)

	def store_result(self, result) -> None:
		"""Store a JSON result of the task in DB"""
		self.db_set("result", frappe.as_json(result))

	def attach_file(
		self,
		file_name: str,
		content: bytes,
		is_private: bool = True,
		doctype: str | None = None,
		docname: str | None = None,
	) -> str:
		"""Attach a file to a document (defaults to the background task) and return its file URL"""
		if not (doctype and docname):
			if self.ref_doctype and self.ref_docname:
				doctype, docname = self.ref_doctype, self.ref_docname

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": doctype or "Background Task",
				"attached_to_name": docname or self.name,
				"content": content,
				"is_private": int(is_private),
			}
		)
		file_doc.insert(ignore_permissions=True)
		return file_doc.file_url

	@staticmethod
	def clear_old_logs(days=7):
		from frappe.query_builder import DocType, Interval
		from frappe.query_builder.functions import Now

		BgTask = DocType("Background Task")
		File = DocType("File")
		cutoff = Now() - Interval(days=days)

		frappe.db.delete(
			File,
			filters=(
				(File.attached_to_doctype == "Background Task")
				& File.attached_to_name.isin(
					frappe.qb.from_(BgTask).select(BgTask.name).where(BgTask.creation < cutoff)
				)
			),
		)

		frappe.db.delete(BgTask, filters=(BgTask.creation < cutoff))

	def _publish(self, message: dict) -> None:
		frappe.publish_realtime(event="task_update", message=message, user=self.user)
		# Cache latest progress/stage for fast lookup on page load
		cache_key = f"background_task:{self.task_id}"
		cached = frappe.cache.get_value(cache_key) or {}
		cached.update(
			{k: v for k, v in message.items() if k not in ("task_id", "task_name") and v is not None}
		)
		frappe.cache.set_value(cache_key, cached, expires_in_sec=3600)


@frappe.whitelist()
def get_recent_tasks(limit: int = 15) -> list[dict]:
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


@frappe.whitelist()
def get_cached_task_status(task_id: str) -> dict | None:
	return frappe.cache.get_value(f"background_task:{task_id}")


@frappe.whitelist()
def stop_task(task_id: str):
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


@frappe.whitelist()
def retry_task(task_id: str):
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
