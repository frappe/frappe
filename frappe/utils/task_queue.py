from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import uuid4

import frappe
from frappe import _

if TYPE_CHECKING:
	from frappe.core.doctype.background_task.background_task import BackgroundTask


def enqueue_task(
	method: str | Callable,
	*,
	task_name: str | None = None,
	queue: str = "default",
	timeout: int | None = None,
	ref_doctype: str | None = None,
	ref_docname: str | None = None,
	deduplicate: bool = False,
	job_id: str | None = None,
	enqueue_after_commit: bool = True,
	now: bool = False,
	on_success: Callable | None = None,
	on_failure: Callable | None = None,
	retry_on: tuple[type[Exception], ...] = (),
	max_retries: int = 0,
	show_progress_bar: bool = True,
	allow_user_cancellation: bool = True,
	allow_user_retry: bool = True,
	at_front: bool = False,
	at_front_when_starved: bool = False,
	**kwargs,
) -> "BackgroundTask":
	"""A wrapper around frappe.enqueue. Enqueue a background job with user-facing tracking"""
	if isinstance(method, Callable):
		method_name = f"{method.__module__}.{method.__qualname__}"
	else:
		method_name = method

	on_success_path = _callback_path(on_success)
	on_failure_path = _callback_path(on_failure)
	rq_retry = _build_rq_retry(retry_on, max_retries)

	if not task_name:
		task_name = method_name

	task_id = str(uuid4())
	user = frappe.session.user

	try:
		arguments_json = frappe.as_json(kwargs) if kwargs else None
	except Exception:
		arguments_json = None

	doc = frappe.new_doc("Background Task")
	doc.task_id = task_id
	doc.job_id = job_id or task_id
	doc.task_name = task_name
	doc.status = "Queued"
	doc.user = user
	doc.method = method_name
	doc.arguments = arguments_json
	doc.queue = queue
	doc.show_progress_bar = show_progress_bar
	doc.allow_user_cancellation = allow_user_cancellation
	doc.allow_user_retry = allow_user_retry
	if ref_doctype:
		doc.ref_doctype = ref_doctype
	if ref_docname:
		doc.ref_docname = ref_docname
	if on_success_path:
		doc.on_success_callback = on_success_path
	if on_failure_path:
		doc.on_failure_callback = on_failure_path
	doc.insert(ignore_permissions=True)

	def _enqueue():
		if frappe.db.get_value("Background Task", {"task_id": task_id}, "status") == "Cancelled":
			return

		frappe.enqueue(
			_execute_task,
			queue=queue,
			timeout=timeout,
			deduplicate=deduplicate,
			job_id=job_id or task_id,
			at_front=at_front,
			now=now,
			at_front_when_starved=at_front_when_starved,
			retry=rq_retry,
			task_id=task_id,
			target_method=method,
			task_user=user,
			task_on_success=on_success_path,
			task_on_failure=on_failure_path,
			task_retry_on=retry_on,
			**kwargs,
		)

	if enqueue_after_commit:
		frappe.db.after_commit.add(_enqueue)
	else:
		_enqueue()

	return doc


def get_current_task() -> "BackgroundTask | None":
	return getattr(frappe.local, "_current_task_handle", None)


def get_task_status(task_id: str) -> dict | None:
	fields = ["status", "progress", "stage", "result", "exception", "started_at", "ended_at"]
	status = frappe.db.get_value("Background Task", {"task_id": task_id}, fields, as_dict=True)
	if not status:
		return None
	cached = frappe.cache.get_value(f"background_task:{task_id}")
	if cached:
		status.update({k: v for k, v in cached.items() if v is not None})
	return status


def _execute_task(
	task_id: str,
	target_method: str | Callable,
	task_user: str,
	task_on_success: str | None = None,
	task_on_failure: str | None = None,
	task_retry_on: tuple[type[Exception], ...] = (),
	**kwargs,
):
	"""Internal wrapper run by the background worker"""
	task_doc = frappe.get_doc("Background Task", {"task_id": task_id})
	if task_doc.status == "Cancelled":
		return

	frappe.local._current_task_handle = task_doc

	is_retry = task_doc.status == "Running"
	task_doc.db_set({"status": "Running", "started_at": frappe.utils.now()})
	frappe.db.commit()

	if not is_retry:
		task_doc._publish({"task_id": task_id, "task_name": task_doc.task_name, "status": "Running"})

	try:
		if isinstance(target_method, str):
			target_method = frappe.get_attr(target_method)

		result = target_method(**kwargs)

		values = {"status": "Completed", "progress": 100, "ended_at": frappe.utils.now()}
		if result is not None:
			try:
				values["result"] = frappe.as_json(result)
			except Exception:
				pass

		task_doc.db_set(values)
		frappe.db.commit()
		task_doc._publish(
			{"task_id": task_id, "task_name": task_doc.task_name, "status": "Completed", "progress": 100}
		)

		if task_on_success:
			_run_callback(task_on_success, task_doc, result=result, task_kwargs=kwargs)

		return result

	except Exception as exc:
		frappe.db.rollback()

		if _should_retry(exc, task_retry_on):
			raise

		_disable_rq_retry()

		if frappe.db.get_value("Background Task", {"task_id": task_id}, "status") == "Cancelled":
			raise

		task_doc.db_set(
			{
				"status": "Failed",
				"exception": frappe.get_traceback(with_context=True),
				"ended_at": frappe.utils.now(),
			}
		)
		frappe.db.commit()

		task_doc._publish({"task_id": task_id, "task_name": task_doc.task_name, "status": "Failed"})

		if task_on_failure:
			_run_callback(task_on_failure, task_doc, exception=exc, task_kwargs=kwargs)

		raise

	finally:
		frappe.local._current_task_handle = None
		frappe.cache.delete_value(f"background_task:{task_id}")


def _build_rq_retry(retry_on: tuple[type[Exception], ...], max_retries: int):
	if retry_on and max_retries > 0:
		from rq import Retry

		return Retry(max=max_retries)
	return None


def _should_retry(exc: Exception, retry_on: tuple[type[Exception], ...]) -> bool:
	if not retry_on or not isinstance(exc, retry_on):
		return False
	job = _current_rq_job()
	return bool(job and getattr(job, "retries_left", None) and job.retries_left > 0)


def _disable_rq_retry() -> None:
	job = _current_rq_job()
	if job and getattr(job, "retries_left", None):
		job.retries_left = 0


def _current_rq_job():
	try:
		from rq import get_current_job

		return get_current_job()
	except Exception:
		return None


def _callback_path(fn: Callable | str | None) -> str | None:
	if fn is None:
		return None
	if isinstance(fn, str):
		return fn
	return f"{fn.__module__}.{fn.__qualname__}"


def _run_callback(callback: str | Callable, task_doc: "BackgroundTask", task_kwargs: dict, **outcome):
	import inspect

	try:
		fn = frappe.get_attr(callback) if isinstance(callback, str) else callback
		context = {"task": task_doc, **outcome, **task_kwargs}
		sig = inspect.signature(fn)
		has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
		fn(**context if has_var_keyword else {k: v for k, v in context.items() if k in sig.parameters})
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Background task callback failed for {task_doc.task_name}")
		frappe.db.commit()
