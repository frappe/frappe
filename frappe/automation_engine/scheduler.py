# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from datetime import datetime, timedelta

import frappe
from frappe.automation_engine import is_enabled
from frappe.automation_engine.dispatch import kick_drainer, matches_rule, queue_trigger
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import parse_cron

QUEUE = "Automation Trigger Queue"
SCHEDULED_PAYLOAD_KEY = "scheduled_fire_at"


def process_cron(now: datetime | None = None):
	"""Queue each due Scheduled automation once for its latest cron fire."""
	if not is_enabled():
		return
	now = frappe.utils.get_datetime(now or frappe.utils.now_datetime())
	queued = 0
	for rule in _scheduled_rules():
		fire_at = _latest_fire(rule.cron_expression, now)
		if fire_at and fire_at >= frappe.utils.get_datetime(rule.creation):
			queued += _queue_rule(rule, fire_at)
	if queued:
		frappe.db.after_commit.add(kick_drainer)


def _scheduled_rules() -> list:
	return frappe.get_all(
		"Automation Flow",
		filters={"enabled": 1, "trigger_type": "Scheduled"},
		fields=["name", "document_type", "cron_expression", "filters", "condition", "creation"],
	)


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
			"status": ("in", ("Pending", "Running")),
		},
		pluck="ref_name",
	)
	completed = frappe.get_all(
		"Automation Run",
		filters={"automation": automation, "creation": (">=", fire_at)},
		pluck="reference_name",
	)
	return {*active, *completed}


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
	if not rule.condition:
		return names
	return [name for name in names if _condition_matches(rule, name)]


def _condition_matches(rule, name: str) -> bool:
	return matches_rule(rule, frappe.get_doc(rule.document_type, name))


def _payload(fire_at: datetime) -> dict:
	return {
		"trigger_type": "Scheduled",
		SCHEDULED_PAYLOAD_KEY: fire_at.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
	}
