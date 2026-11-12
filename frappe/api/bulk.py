"""The shared runner behind every API v2 bulk route.

A route supplies a `BulkAction`; the runner owns the `bulk_actions` gate, the cap, resolving the
selection, the inline-or-background threshold, the Background Task, progress, commits and the result.

	DELETE = BulkAction("Delete", delete_one, check=refuse_without_allow_edit)

	def bulk_delete_docs(doctype):
		return run_bulk(DELETE, doctype)

The result is `{total, done, failed: [{name, error}], queued?}`. `done` and `queued` hold names, or
`{doctype, name}` for a run across doctypes. A run where records fail still ends `Completed`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

import frappe
from frappe import _, cint
from frappe.api.utils import FrappeValueError, apply_controller_get_list
from frappe.database.utils import DefaultOrderBy
from frappe.model.utils import is_virtual_doctype
from frappe.utils import strip_html_tags
from frappe.utils.task_queue import enqueue_task, get_current_task

DEFAULT_LIMIT = 500
DEFAULT_THRESHOLD = 20
# A record function returns this when the work is queued elsewhere, so the result does not call it done.
QUEUED = "queued"


@dataclass(frozen=True)
class BulkAction:
	"""What an action plugs in with.

	`run(doctype, name, **params)` acts on one record and raises to fail it. It must be module-level:
	the worker imports it by path. `check(doctype, params)` refuses the whole run before any record.
	`finish(params, result)` runs once after the last record and returns keys to add to the result.
	`background` skips the inline path: the run always queues.
	"""

	label: str
	run: Callable
	check: Callable[[str, dict], None] | None = None
	finish: Callable[[dict, dict], dict | None] | None = None
	background: bool = False

	def __post_init__(self):
		for function in (self.run, self.finish):
			if function and ("<" in function.__qualname__ or "." in function.__qualname__):
				raise ValueError("A bulk action's functions must be module-level functions")

	@property
	def path(self) -> str:
		return path_of(self.run)

	@property
	def finish_path(self) -> str | None:
		return path_of(self.finish) if self.finish else None


class Record(NamedTuple):
	doctype: str
	name: str
	# Per-record arguments, merged over the run's params.
	kwargs: dict | None = None


class Selection(NamedTuple):
	records: list[Record]
	# Entries the body got wrong, reported as failed without running.
	rejected: list[dict]


def run_bulk(
	action: BulkAction,
	doctype: str | None = None,
	*,
	selection: Selection | None = None,
	params: dict | None = None,
	limit: int | None = None,
) -> dict:
	"""Run `action` on the selection in the request body, inline or as a Background Task.

	`doctype` is None for a run across doctypes, which needs a `selection` of its own. A body with
	`names` or `filters` and `or_filters` is read when no `selection` is given. `limit` replaces the
	site cap for an action with a cap of its own.
	"""
	check_gate()
	params = params or {}
	limit = limit or get_limit()
	selection = selection or read_selection(doctype, limit)
	total = len(selection.records) + len(selection.rejected)
	check_cap(total, limit)

	if action.check:
		for dt in {doctype, *(record.doctype for record in selection.records)} - {None}:
			action.check(dt, params)

	if total <= get_async_threshold(doctype) and not action.background:
		return run_records(action.run, selection, params, cross_doctype=doctype is None, finish=action.finish)

	return enqueue_run(action, doctype, selection, params)


def has_gate() -> bool:
	return bool(cint(frappe.get_cached_value("User", frappe.session.user, "bulk_actions")))


def check_gate():
	if not has_gate():
		frappe.throw(_("You are not allowed to run bulk actions."), frappe.PermissionError)


def get_limit() -> int:
	return cint(frappe.conf.get("bulk_operation_limit", DEFAULT_LIMIT))


def get_async_threshold(doctype: str | None = None) -> int:
	conf = frappe.conf.get("bulk_operation_async_threshold", DEFAULT_THRESHOLD)

	if isinstance(conf, dict):
		value = conf.get(doctype, DEFAULT_THRESHOLD) if doctype else conf.get("*", DEFAULT_THRESHOLD)
	else:
		value = conf

	return cint(value)


def check_cap(total: int, limit: int):
	if total > limit:
		frappe.throw(
			_("Too many documents: a bulk action runs on at most {0} at a time.").format(limit),
			title=_("Too Many Documents"),
		)


def read_selection(doctype: str, limit: int | None = None) -> Selection:
	"""`{names}` or `{filters, or_filters}` from the request body; filters follow the list's rules."""
	form = frappe.form_dict

	if "names" in form:
		return selection_from_names(doctype, form.get("names"))

	if "filters" in form or "or_filters" in form:
		filters = frappe.parse_json(form.get("filters"))
		or_filters = frappe.parse_json(form.get("or_filters"))
		for key, value in (("filters", filters), ("or_filters", or_filters)):
			if value and not isinstance(value, list | dict):
				raise FrappeValueError(f"'{key}' must be a list or dictionary")

		return Selection(
			[Record(doctype, name) for name in resolve_names(doctype, filters, or_filters, limit)], []
		)

	raise FrappeValueError("'names' must be a list")


def selection_from_names(doctype: str, names) -> Selection:
	if not isinstance(names, list):
		raise FrappeValueError("'names' must be a list")

	records, rejected = [], []
	for name in names:
		if isinstance(name, str | int):
			records.append(Record(doctype, str(name)))
		else:
			rejected.append({"name": name, "error": "'name' must be a string or integer"})

	return Selection(records, rejected)


def resolve_names(doctype: str, filters, or_filters, limit: int | None = None) -> list[str]:
	"""The names a list with these filters shows the session user, one past the cap so the cap can refuse."""
	limit = (limit or get_limit()) + 1

	if is_virtual_doctype(doctype):
		rows = frappe.get_list(doctype, fields=["name"], filters=filters, or_filters=or_filters, limit=limit)
	else:
		query = frappe.qb.get_query(
			table=doctype,
			fields=["name"],
			filters=filters,
			or_filters=or_filters,
			order_by=DefaultOrderBy,
			limit=limit,
			ignore_permissions=False,
		)
		rows = apply_controller_get_list(doctype, query).run(as_dict=True)

	return [str(row["name"]) for row in rows]


def enqueue_run(action: BulkAction, doctype: str | None, selection: Selection, params: dict) -> dict:
	task = enqueue_task(
		"frappe.api.bulk.run_task",
		task_name=f"{action.label} {doctype or _('documents')}",
		queue="long",
		allow_user_retry=False,  # a retry would run the whole selection again
		ref_doctype=doctype,
		action=action.path,
		records=[list(record) for record in selection.records],
		rejected=selection.rejected,
		params=params,
		cross_doctype=doctype is None,
		finish=action.finish_path,
	)
	frappe.response.http_status_code = 202
	return {"task_id": task.task_id, "job_id": task.job_id}


def run_task(
	action: str, records: list, rejected: list, params: dict, cross_doctype: bool, finish: str | None = None
) -> dict:
	"""The worker side of `enqueue_run`; its return value is stored as the Background Task result."""
	selection = Selection([Record(*record) for record in records], rejected)
	return run_records(
		frappe.get_attr(action),
		selection,
		params,
		cross_doctype,
		task=get_current_task(),
		finish=frappe.get_attr(finish) if finish else None,
	)


def reason_of(e: Exception) -> str:
	"""One line for the result panel; a missing record raises with no message."""
	reason = strip_html_tags(str(e)).strip()
	if reason:
		return reason
	return _("Not found") if isinstance(e, frappe.DoesNotExistError) else _("Failed without a reason")


def run_records(
	run_one: Callable,
	selection: Selection,
	params: dict,
	cross_doctype: bool,
	task=None,
	finish: Callable | None = None,
) -> dict:
	"""Run each record under a savepoint. A Background Task commits after every record."""
	done, queued, failed = [], [], list(selection.rejected)
	total = len(selection.records) + len(failed)

	for index, record in enumerate(selection.records, start=1):
		frappe.db.savepoint("bulk_record")
		try:
			outcome = run_one(record.doctype, record.name, **{**params, **(record.kwargs or {})})
		except Exception as e:
			frappe.db.rollback(save_point="bulk_record")
			frappe.clear_last_message()
			failed.append({**identity_of(record, cross_doctype), "error": reason_of(e)})
		else:
			(queued if outcome == QUEUED else done).append(ref_of(record, cross_doctype))

		if task:
			frappe.db.commit()  # nosemgrep
			processed = len(selection.rejected) + index
			task.publish_progress(processed * 100 / total, _("{0} of {1}").format(processed, total))

	result = {"total": total, "done": done, "failed": failed}
	if queued:
		result["queued"] = queued
	if finish:
		result.update(finish(params, result) or {})
	return result


def path_of(function: Callable) -> str:
	return f"{function.__module__}.{function.__qualname__}"


def ref_of(record: Record, cross_doctype: bool) -> str | dict:
	return identity_of(record, cross_doctype) if cross_doctype else record.name


def identity_of(record: Record, cross_doctype: bool) -> dict:
	identity = {"name": record.name}
	if cross_doctype:
		identity["doctype"] = record.doctype
	return identity
