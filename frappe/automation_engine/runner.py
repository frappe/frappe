# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Executes a claimed outbox row: builds a run log, runs each action under its own
savepoint, and records the outcome. Bookkeeping never saves the Automation Flow doc — the
circuit breaker lives in Redis, and auto-disable uses db.set_value(update_modified=False).
"""

import time

import frappe
from frappe import _
from frappe.automation_engine.actions.base import StopAutomation, get_action_registry

QUEUE = "Automation Trigger Queue"
DEFAULT_FAILURE_THRESHOLD = 10


def execute_automation(queue_name: str):
	row = frappe.get_doc(QUEUE, queue_name)
	rule = frappe.get_cached_doc("Automation Flow", row.automation)
	doc = _load_target(row)
	run = _create_run(rule, row)

	if doc is None:
		return _finalize(run, rule, row, "Skipped", error="Target document not found")

	previous_depth = frappe.flags.get("automation_depth", 0)
	frappe.flags.automation_depth = frappe.utils.cint(row.depth)
	try:
		status = _run_steps(run, rule, doc)
	finally:
		frappe.flags.automation_depth = previous_depth

	_finalize(run, rule, row, status)


def _load_target(row):
	if not row.ref_name:
		return None
	try:
		return frappe.get_doc(row.ref_doctype, row.ref_name)
	except frappe.DoesNotExistError:
		return None


def _create_run(rule, row):
	run = frappe.new_doc("Automation Run")
	run.update(
		{
			"automation": rule.name,
			"automation_title": rule.title,
			"reference_doctype": row.ref_doctype,
			"reference_name": row.ref_name,
			"status": "Running",
			"depth": frappe.utils.cint(row.depth),
			"started_at": frappe.utils.now(),
			"actions_snapshot": frappe.as_json(
				[{"action_type": a.action_type, "params": a.params} for a in rule.actions]
			),
		}
	)
	# The referenced doc may legitimately be gone (deleted, or a Doc Deleted trigger); the
	# run log must record it regardless, so skip Dynamic Link existence validation.
	run.flags.ignore_links = True
	return run.insert(ignore_permissions=True)


def _run_steps(run, rule, doc) -> str:
	registry = get_action_registry()
	overall = "Success"
	for idx, action in enumerate(rule.actions):
		status, detail, duration = _run_one(registry, action, doc, run, rule, idx)
		run.append(
			"steps",
			{
				"step_idx": idx,
				"action_type": action.action_type,
				"status": status,
				"detail": (detail or "")[:5000],
				"duration_ms": duration,
			},
		)
		if status == "Failed":
			overall = "Partially Failed"
			if rule.stop_on_error:
				return "Failed"
	return overall


def _run_one(registry, action, doc, run, rule, idx):
	started = time.monotonic()
	savepoint = f"auto_step_{idx}"
	handler = registry.get(action.action_type)
	params = frappe.parse_json(action.params) if action.params else {}
	context = {"run": run, "rule": rule}

	# A concurrent write between claim and save raises TimestampMismatch
	# reload and retry once.
	for last_attempt in (False, True):
		frappe.db.savepoint(savepoint)
		try:
			if not handler:
				raise ValueError(f"Unknown action type: {action.action_type}")
			detail = handler.execute(doc, params or {}, context)
			return "Success", detail, _ms(started)
		except StopAutomation:
			raise
		except frappe.TimestampMismatchError:
			frappe.db.rollback(save_point=savepoint)
			if last_attempt:
				return "Failed", frappe.get_traceback(), _ms(started)
			doc.reload()
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			return "Failed", frappe.get_traceback(), _ms(started)


def _ms(started) -> int:
	return int((time.monotonic() - started) * 1000)


def _finalize(run, rule, row, status, error=None):
	run.status = status
	run.ended_at = frappe.utils.now()
	if error:
		run.error_summary = error
	elif status in ("Failed", "Partially Failed"):
		run.error_summary = _first_error(run)
	run.save(ignore_permissions=True)

	if status == "Failed":
		_record_failure(rule)
	elif status == "Success":
		_reset_failures(rule)

	# Completed runs (Success / Partially Failed) drop their queue row — detail lives in the
	# Run log. Failed (stopped) and Skipped rows are retained for the purge sweep.
	if status in ("Success", "Partially Failed"):
		frappe.delete_doc(QUEUE, row.name, ignore_permissions=True, force=True)
	else:
		frappe.db.set_value(QUEUE, row.name, "status", status, update_modified=False)

	frappe.publish_realtime(
		"automation_run_update",
		{"automation": rule.name, "run": run.name, "status": status},
		doctype=run.reference_doctype,
		docname=run.reference_name,
	)


def _first_error(run) -> str:
	for step in run.steps:
		if step.status == "Failed":
			return (step.detail or "").splitlines()[-1][:140] if step.detail else "Failed"
	return "Failed"


def _failure_key(rule_name) -> str:
	return f"automation_failures::{frappe.local.site}::{rule_name}"


def _record_failure(rule):
	threshold = frappe.conf.get("automation_failure_threshold") or DEFAULT_FAILURE_THRESHOLD
	if frappe.cache.incr(_failure_key(rule.name)) >= threshold:
		_trip_breaker(rule, threshold)


def _reset_failures(rule):
	frappe.cache.delete(_failure_key(rule.name))


def _trip_breaker(rule, threshold):
	from frappe.automation_engine.registry import clear_automation_cache

	reason = _("Auto-disabled after {0} consecutive failures").format(threshold)
	frappe.db.set_value(
		"Automation Flow", rule.name, {"enabled": 0, "disabled_reason": reason}, update_modified=False
	)
	# Drop the orphaned backlog in one UPDATE, the rule won't run again.
	frappe.db.set_value(
		QUEUE, {"automation": rule.name, "status": "Pending"}, "status", "Skipped", update_modified=False
	)
	clear_automation_cache(rule.document_type)
	frappe.cache.delete(_failure_key(rule.name))
	_notify_owner(rule, reason)


def _notify_owner(rule, reason):
	owner = frappe.db.get_value("Automation Flow", rule.name, "owner")
	if not owner:
		return
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": owner,
			"type": "Alert",
			"subject": _("Automation Flow {0} was auto-disabled").format(rule.title),
			"email_content": reason,
			"document_type": "Automation Flow",
			"document_name": rule.name,
		}
	).insert(ignore_permissions=True)
