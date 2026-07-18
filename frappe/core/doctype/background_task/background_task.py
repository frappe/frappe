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


# `get_recent_tasks`, `get_cached_task_status`, `stop_task`, `retry_task` moved to frappe.core.api.background_jobs.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_BACKGROUND_JOBS_API = {
	"get_recent_tasks": "get_recent_tasks",
	"get_cached_task_status": "get_cached_task_status",
	"stop_task": "stop_task",
	"retry_task": "retry_task",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_BACKGROUND_JOBS_API.get(name):
		from frappe.core.api import background_jobs

		return getattr(background_jobs, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
