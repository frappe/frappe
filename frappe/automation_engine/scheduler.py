# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from datetime import datetime, timedelta

import frappe
from frappe.automation_engine import WAITING_STATES, is_enabled
from frappe.automation_engine.conditions import condition_fieldnames
from frappe.automation_engine.dispatch import kick_drainer, matches_rule, queue_trigger
from frappe.automation_engine.runner import TASK_METHOD, automation_task_name
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import parse_cron

QUEUE = "Automation Trigger Queue"
SCHEDULED_PAYLOAD_KEY = "scheduled_fire_at"
RUN_LOOKUP_INDEX = "automation_run_lookup"


def process_cron(now: datetime | None = None):
	"""Queue each due Scheduled automation once for its latest cron fire."""
	if not is_enabled():
		return
	now = frappe.utils.get_datetime(now or frappe.utils.now_datetime())
	queued = 0
	for rule in _due_scheduled_rules(now):
		fire_at = _latest_fire(rule.cron_expression, now)
		if fire_at and fire_at >= frappe.utils.get_datetime(rule.creation):
			queued += _queue_rule(rule, fire_at)
		# Advance regardless of whether anything was queued: a fire that predates the rule,
		# or one the dedup already covers, still retires this slot. Leaving next_run behind
		# would put the rule back in the due set on every following tick.
		set_next_run(rule.name, rule.cron_expression, now)
	if queued:
		frappe.db.after_commit.add(kick_drainer)


def _due_scheduled_rules(now: datetime) -> list:
	"""Rules whose next fire has arrived.

	The gate is the point of the field: without it every tick scans each rule's target
	DocType, 288 times a day, to rediscover work a once-daily rule does not have. A NULL
	next_run counts as due so a flow saved before the field existed keeps firing.
	"""
	return frappe.get_all(
		"Automation Flow",
		filters={"enabled": 1, "trigger_type": "Scheduled"},
		or_filters=[["next_run", "is", "not set"], ["next_run", "<=", now]],
		fields=["name", "document_type", "cron_expression", "filters", "condition", "creation"],
	)


def set_next_run(automation: str, expression: str, after: datetime | None = None):
	"""Store the next fire due strictly after `after`.

	Written with update_modified=False: this is scheduler bookkeeping, and bumping the flow
	would invalidate the cached rule registry on every tick.
	"""
	frappe.db.set_value(
		"Automation Flow",
		automation,
		"next_run",
		next_fire(expression, after or frappe.utils.now_datetime()),
		update_modified=False,
	)


def next_fire(expression: str, after: datetime) -> datetime | None:
	if not expression:
		return None
	return parse_cron(expression).get_next(datetime, start_time=after)


def _latest_fire(expression: str, now: datetime) -> datetime | None:
	if not expression:
		return None
	return parse_cron(expression).get_prev(
		datetime,
		start_time=now + timedelta(seconds=1),
	)


def _handled_names(automation: str, fire_at: datetime) -> set[str | None]:
	active = frappe.get_all(
		QUEUE,
		filters={
			"automation": automation,
			"status": ("in", (*WAITING_STATES, "Running")),
		},
		pluck="ref_name",
	)
	completed = _completed_names(automation, fire_at)
	return {*active, *completed}


def ensure_run_lookup_index():
	"""Index the dedup lookup `_completed_names` runs on every scheduled tick.

	Background Task carries no index of its own and grows with every automation run, so
	without this the dedup check degrades into a full scan as history accumulates.
	"""
	table = "tabBackground Task"
	if not frappe.db.has_index(table, RUN_LOOKUP_INDEX):
		frappe.db.sql_ddl(
			f"ALTER TABLE `{table}` ADD INDEX `{RUN_LOOKUP_INDEX}` (`task_name`, `method`, `creation`)"
		)


def _completed_names(automation: str, fire_at: datetime) -> list[str | None]:
	task = frappe.qb.DocType("Background Task")
	return (
		frappe.qb.from_(task)
		.select(task.ref_docname)
		.where(task.task_name == automation_task_name(automation))
		.where(task.method == TASK_METHOD)
		.where(task.creation >= fire_at)
		.run(pluck=True)
	)


def _queue_rule(rule, fire_at: datetime) -> int:
	if rule.document_type:
		return _queue_matching_docs(rule, fire_at)
	if None in _handled_names(rule.name, fire_at):
		return 0
	queue_trigger(rule.name, None, None, payload=_payload(fire_at))
	return 1


def _queue_matching_docs(rule, fire_at: datetime) -> int:
	names = _matching_names(rule)
	if not names:
		return 0
	handled = _handled_names(rule.name, fire_at)
	queued = 0
	for name in names:
		if name in handled:
			continue
		queue_trigger(rule.name, rule.document_type, name, payload=_payload(fire_at))
		queued += 1
	return queued


def _matching_names(rule) -> list[str]:
	filters = frappe.parse_json(rule.filters) if rule.filters else None
	names = frappe.get_all(rule.document_type, filters=filters, pluck="name")
	return _condition_filtered(rule, names)


def _condition_filtered(rule, names: list[str]) -> list[str]:
	"""Narrow `names` by the rule's condition, loading the candidates in one query when it can.

	A condition that only reads plain columns is answered from a single bulk fetch. Anything
	else - a child table, a method call, an unparseable expression - still gets the real
	document, because a field row cannot stand in for one.
	"""
	if not rule.condition:
		return names
	fields = _condition_columns(rule)
	if fields is None:
		return [name for name in names if matches_rule(rule, _load(rule, name))]
	return [row.name for row in _condition_rows(rule, names, fields) if matches_rule(rule, row)]


def _condition_rows(rule, names: list[str], fields: set[str]) -> list:
	if not names:
		return []
	rows = frappe.get_all(
		rule.document_type,
		filters=[["name", "in", names]],
		fields=["name", *sorted(fields)],
	)
	for row in rows:
		# evaluate_filters reads doctype off the row to resolve short-form filters.
		row.doctype = rule.document_type
	return rows


def _condition_columns(rule) -> set[str] | None:
	"""Columns the rule's condition and filters read, or None when a bulk fetch cannot serve it."""
	names = condition_fieldnames(rule.condition)
	if names is None:
		return None
	names |= _filter_fieldnames(frappe.parse_json(rule.filters) if rule.filters else None)
	valid = set(frappe.get_meta(rule.document_type).get_valid_columns())
	return names if names <= valid else None


def _filter_fieldnames(stored) -> set[str]:
	"""Filters are re-checked against the loaded row, so their fields have to come along."""
	if not stored:
		return set()
	if isinstance(stored, dict):
		return set(stored.keys())
	# A filter row is [fieldname, operator, value] or [doctype, fieldname, operator, value].
	return {row[1] if len(row) > 3 else row[0] for row in stored if isinstance(row, list | tuple)}


def _load(rule, name: str):
	return frappe.get_doc(rule.document_type, name)


def _payload(fire_at: datetime) -> dict:
	return {
		"trigger_type": "Scheduled",
		SCHEDULED_PAYLOAD_KEY: fire_at.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
	}


def process_date_based(now: datetime | None = None):
	"""Queue Date Based automations for documents whose date field lands on today's offset.

	Runs hourly, but each document fires at most once per occurrence: the dedup window is
	the whole of today (in site time), so the remaining ticks find the run already recorded.
	"""
	if not is_enabled():
		return
	today = frappe.utils.getdate(now or frappe.utils.now_datetime())
	queued = sum(_queue_date_rule(rule, today) for rule in _date_based_rules())
	if queued:
		frappe.db.after_commit.add(kick_drainer)


def _date_based_rules() -> list:
	return frappe.get_all(
		"Automation Flow",
		filters={"enabled": 1, "trigger_type": "Date Based"},
		fields=[
			"name",
			"document_type",
			"date_field",
			"date_offset",
			"date_direction",
			"filters",
			"condition",
		],
	)


def _queue_date_rule(rule, today) -> int:
	if not (rule.document_type and rule.date_field):
		return 0
	handled = _handled_names(rule.name, frappe.utils.get_datetime(f"{today} 00:00:00"))
	queued = 0
	for name in _due_names(rule, _target_date(rule, today)):
		if name in handled:
			continue
		queue_trigger(rule.name, rule.document_type, name, payload=_date_payload(rule, today))
		queued += 1
	return queued


def _target_date(rule, today):
	""" "3 days Before renewal" is due today when renewal is 3 days out; After looks back."""
	offset = frappe.utils.cint(rule.date_offset)
	if rule.date_direction == "After":
		offset = -offset
	return frappe.utils.add_days(today, offset)


def _due_names(rule, target) -> list[str]:
	# `between` on the whole day covers Date and Datetime fields alike.
	filters = [
		*_normalize_filters(frappe.parse_json(rule.filters) if rule.filters else None),
		[rule.date_field, "between", [f"{target} 00:00:00", f"{target} 23:59:59"]],
	]
	names = frappe.get_all(rule.document_type, filters=filters, pluck="name")
	return _condition_filtered(rule, names)


def _normalize_filters(stored) -> list:
	"""Rule filters are stored as a filter group or a dict; combining needs a plain list."""
	if not stored:
		return []
	if not isinstance(stored, dict):
		return list(stored)
	return [
		[field, *value] if isinstance(value, list | tuple) else [field, "=", value]
		for field, value in stored.items()
	]


def _date_payload(rule, today) -> dict:
	return {
		"trigger_type": "Date Based",
		"date_field": rule.date_field,
		"occurrence_date": str(today),
	}
