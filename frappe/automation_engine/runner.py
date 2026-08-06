# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Executes a claimed outbox row: creates a Background Task, runs each action under its own
savepoint, and records the outcome. Bookkeeping never saves the Automation Flow doc — the
circuit breaker lives in Redis, and auto-disable uses db.set_value(update_modified=False).

Steps run off an `actions_snapshot` taken at run start and stored in the Background Task's
arguments. `If` steps pick an arm, and every step carrying that `parent_step` in the other
arm is passed over — not run, and not logged.
"""

import time

import frappe
from frappe import _
from frappe.automation_engine.actions.base import StopAutomation, get_action_registry
from frappe.automation_engine.dispatch import matches_rule

QUEUE = "Automation Trigger Queue"
TASK_METHOD = "frappe.automation_engine.runner.execute_automation"
TASK_NAME_PREFIX = "Automation Flow: "
DEFAULT_FAILURE_THRESHOLD = 10


def execute_automation(queue_name: str):
	row = frappe.get_doc(QUEUE, queue_name)
	rule = frappe.get_cached_doc("Automation Flow", row.automation)
	doc = _load_target(row)
	snapshot = [_action_snapshot(action) for action in rule.actions]
	run = _create_run(rule, row, snapshot)
	steps = []

	if doc is None and row.ref_name:
		return _finalize(run, rule, row, "Skipped", steps, error="Target document not found")
	if rule.revalidate_on_run and doc and not matches_rule(rule, doc):
		return _finalize(run, rule, row, "Skipped", steps, error="Rule no longer matches")
	if rule.log_only:
		_simulate_steps(steps, snapshot)
		return _finalize(run, rule, row, "Simulated", steps)

	previous_depth = frappe.flags.get("automation_depth", 0)
	frappe.flags.automation_depth = frappe.utils.cint(row.depth)
	try:
		status = _run_plan(steps, rule, doc, _context(row, run, rule), snapshot)
	finally:
		frappe.flags.automation_depth = previous_depth

	_finalize(run, rule, row, status, steps)


def _load_target(row):
	if not row.ref_name:
		return None
	try:
		return frappe.get_doc(row.ref_doctype, row.ref_name)
	except frappe.DoesNotExistError:
		return None


def _create_run(rule, row, snapshot):
	run = frappe.new_doc("Background Task")
	run.update(_task_values(rule, row, snapshot))
	# The referenced doc may legitimately be gone (deleted, or a Doc Deleted trigger); the
	# task must record it regardless, so skip Dynamic Link existence validation.
	run.flags.ignore_links = True
	return run.insert(ignore_permissions=True)


def _task_values(rule, row, snapshot) -> dict:
	return {
		"task_id": frappe.generate_hash(length=20),
		"job_id": row.name,
		"task_name": automation_task_name(rule.name),
		"user": frappe.session.user or "Administrator",
		"method": TASK_METHOD,
		"status": "Running",
		"queue": "default",
		"ref_doctype": row.ref_doctype,
		"ref_docname": row.ref_name,
		"started_at": frappe.utils.now(),
		"arguments": frappe.as_json(_task_arguments(rule, row, snapshot)),
		"show_progress_bar": 0,
		"allow_user_cancellation": 0,
		"allow_user_retry": 0,
	}


def _task_arguments(rule, row, snapshot) -> dict:
	return {
		"automation": rule.name,
		"automation_title": rule.title,
		"depth": frappe.utils.cint(row.depth),
		"event_payload": frappe.parse_json(row.event_payload) if row.event_payload else {},
		"actions_snapshot": snapshot,
	}


def _action_snapshot(action) -> dict:
	return {
		"idx": frappe.utils.cint(action.idx),
		"step_type": action.step_type or "Action",
		"action_type": action.action_type,
		"params": action.params,
		"step_condition": action.step_condition,
		"parent_step": frappe.utils.cint(action.parent_step),
		"branch": action.branch or "",
	}


def automation_task_name(automation: str) -> str:
	return f"{TASK_NAME_PREFIX}{automation}"


def _context(row, run, rule) -> dict:
	return {
		"payload": frappe.parse_json(row.event_payload) if row.event_payload else {},
		"queue_row": row,
		"run": run,
		"rule": rule,
	}


def _run_plan(steps, rule, doc, context, snapshot) -> str:
	"""Walk the snapshot once, running only the steps on the taken branch arms."""
	registry = get_action_registry()
	taken: dict = {}
	overall = "Success"
	for pos, step in enumerate(snapshot):
		status, detail, duration = _step_outcome(registry, step, doc, context, pos, taken)
		if status is None:
			continue
		_append_step(steps, step, pos, status, detail, duration)
		if status == "Waiting":
			return "Waiting"
		if status == "Failed":
			overall = "Partially Failed"
			if rule.stop_on_error:
				return "Failed"
	return overall


def _step_outcome(registry, step, doc, context, pos, taken):
	"""Resolve one plan entry. A None status means it is not on this run's path at all."""
	if not _branch_active(step, taken):
		return None, None, None
	step_type = step.get("step_type") or "Action"
	if step_type == "If":
		return _resolve_if(step, doc, context, taken)
	if not _step_condition_matches(step, doc, context):
		return "Skipped", _("Step condition did not match"), 0
	if step_type == "Wait":
		return "Waiting", _("Wait resume is not enabled yet"), 0
	return _run_one(registry, step, doc, context, pos)


def _branch_active(step, taken) -> bool:
	"""True when the enclosing If (if any) chose the arm this step sits in."""
	parent = frappe.utils.cint(step.get("parent_step"))
	if not parent:
		return True
	if parent not in taken:
		return False  # the enclosing If was itself on an arm that wasn't taken
	return (step.get("branch") or "If") == taken[parent]


def _resolve_if(step, doc, context, taken):
	"""Pick the arm for an If step; its children consult `taken` by the If's own idx."""
	arm = "If" if _step_condition_matches(step, doc, context) else "Else"
	taken[frappe.utils.cint(step.get("idx"))] = arm
	return "Success", _("Condition took the {0} branch").format(arm), 0


def _run_one(registry, step, doc, context, idx):
	started = time.monotonic()
	savepoint = f"auto_step_{idx}"
	handler = registry.get(step.get("action_type"))
	params = _step_params(step)

	# A concurrent write between claim and save raises TimestampMismatch
	# reload and retry once.
	for last_attempt in (False, True):
		frappe.db.savepoint(savepoint)
		try:
			if not handler:
				raise ValueError(f"Unknown action type: {step.get('action_type')}")
			detail = handler.execute(doc, params, context)
			return "Success", detail, _ms(started)
		except StopAutomation:
			return "Waiting", _("Automation paused"), _ms(started)
		except frappe.TimestampMismatchError:
			frappe.db.rollback(save_point=savepoint)
			if last_attempt:
				return "Failed", frappe.get_traceback(), _ms(started)
			doc.reload()
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			return "Failed", frappe.get_traceback(), _ms(started)


def _step_params(step) -> dict:
	params = step.get("params")
	return (frappe.parse_json(params) if isinstance(params, str) else params) or {}


def _step_condition_matches(step, doc, context) -> bool:
	condition = step.get("step_condition")
	if not condition:
		return True
	return bool(frappe.safe_eval(condition, None, {"doc": doc, "context": context}))


def _append_step(steps, step, idx, status, detail, duration):
	detail, output = _action_result(detail)
	steps.append(
		{
			"step_idx": idx,
			"action_type": step.get("action_type") or step.get("step_type") or "Action",
			"status": status,
			"detail": (detail or "")[:5000],
			"output": output,
			"duration_ms": duration,
		}
	)


def _action_result(result):
	if not isinstance(result, dict):
		return result, None
	detail = result.get("detail") or result.get("destination_reference") or _("Action completed")
	return str(detail), result


def _simulate_steps(steps, snapshot):
	for idx, step in enumerate(snapshot):
		_append_step(steps, step, idx, "Skipped", _("Simulated: action was not executed"), 0)


def _ms(started) -> int:
	return int((time.monotonic() - started) * 1000)


def _finalize(run, rule, row, status, steps, error=None):
	error_summary = error or _error_summary(status, steps)
	run.update(
		{
			"status": "Failed" if status == "Failed" else "Completed",
			"ended_at": frappe.utils.now(),
			"progress": 100,
			"result": frappe.as_json(_run_result(rule, row, status, steps, error_summary)),
			"exception": _first_error_detail(steps) if status == "Failed" else None,
		}
	)
	run.save(ignore_permissions=True)

	if status == "Failed":
		_record_failure(rule)
	elif status in ("Success", "Simulated"):
		_reset_failures(rule)

	# Completed runs drop their queue row because detail lives in the Background Task result.
	# Failed (stopped) and Skipped rows are retained for the purge sweep.
	if status in ("Success", "Partially Failed", "Simulated"):
		frappe.delete_doc(QUEUE, row.name, ignore_permissions=True, force=True)
	else:
		queue_status = "Done" if status == "Waiting" else status
		frappe.db.set_value(QUEUE, row.name, "status", queue_status, update_modified=False)

	frappe.publish_realtime(
		"automation_run_update",
		{"automation": rule.name, "run": run.name, "status": status},
		doctype=run.ref_doctype,
		docname=run.ref_docname,
	)


def _run_result(rule, row, status, steps, error_summary) -> dict:
	return {
		"automation": rule.name,
		"automation_title": rule.title,
		"automation_status": status,
		"depth": frappe.utils.cint(row.depth),
		"error_summary": error_summary,
		"steps": steps,
	}


def _error_summary(status, steps) -> str | None:
	if status not in ("Failed", "Partially Failed"):
		return None
	detail = _first_error_detail(steps)
	return detail.splitlines()[-1][:140] if detail else "Failed"


def _first_error_detail(steps) -> str | None:
	for step in steps:
		if step["status"] == "Failed":
			return step["detail"] or "Failed"
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
