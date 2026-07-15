# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from datetime import datetime, timedelta

from croniter import croniter

import frappe
from frappe.automation_engine.dispatch import kick_drainer, matches_rule, queue_trigger

QUEUE = "Automation Trigger Queue"
SCHEDULED_PAYLOAD_KEY = "scheduled_fire_at"


def process_cron(now: datetime | None = None):
	"""Queue each due Scheduled automation once for its latest cron fire."""
	now = frappe.utils.get_datetime(now or frappe.utils.now_datetime())
	queued = 0
	for rule in _scheduled_rules():
		fire_at = _latest_fire(rule.cron_expression, now)
		if fire_at:
			queued += _queue_rule(rule, fire_at)
	if queued:
		frappe.db.after_commit.add(kick_drainer)


def _scheduled_rules() -> list:
	return frappe.get_all(
		"Automation Flow",
		filters={"enabled": 1, "trigger_type": "Scheduled"},
		fields=["name", "document_type", "cron_expression", "filters", "condition"],
	)


def _latest_fire(expression: str, now: datetime) -> datetime | None:
	if not expression:
		return None
	return croniter(expression, now + timedelta(seconds=1)).get_prev(datetime)


def _already_handled(rule, fire_at: datetime, docname: str | None = None) -> bool:
	return _has_active_queue(rule.name, docname) or _has_run_since(rule.name, fire_at, docname)


def _has_active_queue(automation: str, docname: str | None) -> bool:
	return bool(
		frappe.db.exists(
			QUEUE,
			{
				"automation": automation,
				"ref_name": docname or ("is", "not set"),
				"status": ("in", ("Pending", "Running")),
			},
		)
	)


def _has_run_since(automation: str, fire_at: datetime, docname: str | None) -> bool:
	return bool(frappe.db.exists("Automation Run", _run_filters(automation, fire_at, docname)))


def _run_filters(automation: str, fire_at: datetime, docname: str | None) -> dict:
	return {
		"automation": automation,
		"reference_name": docname or ("is", "not set"),
		"creation": (">=", fire_at),
	}


def _queue_rule(rule, fire_at: datetime) -> int:
	if rule.document_type:
		return _queue_matching_docs(rule, fire_at)
	if _already_handled(rule, fire_at):
		return 0
	queue_trigger(rule.name, None, None, payload=_payload(fire_at))
	return 1


def _queue_matching_docs(rule, fire_at: datetime) -> int:
	queued = 0
	for name in _matching_names(rule):
		if _already_handled(rule, fire_at, name):
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
