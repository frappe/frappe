# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import time
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.automation_engine import settings
from frappe.automation_engine.actions.base import StopAutomation, get_action_registry
from frappe.automation_engine.conditions import condition_values, evaluate_related_condition
from frappe.automation_engine.dispatch import matches_rule
from frappe.automation_engine.events import get_wait_outcome, schedule_event_wait
from frappe.automation_engine.queue import QUEUE, WAITING_STATES, queue_status
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.relationships import load_record, resolve_relationships
from frappe.utils import add_to_date, cint, now

TASK_METHOD = "frappe.automation_engine.runner.execute_automation"
TASK_NAME_PREFIX = "Automation Flow: "
WAIT_UNIT_SECONDS = {"Seconds": 1, "Minutes": 60, "Hours": 3600, "Days": 86400}


def execute_automation(queue_name: str):
	row = frappe.get_doc(QUEUE, queue_name)
	# Settle any event wait this row is resuming before the plan reads its outcome.
	event = get_wait_outcome(row) if row.resume_run else None
	rule = frappe.get_cached_doc("Automation Flow", row.automation)
	doc = _load_target(row)
	run, steps, snapshot = _run_state(rule, row, doc)

	if doc is None and row.ref_doctype and row.ref_name:
		return _finalize(run, rule, row, "Skipped", steps, error="Target document not found")
	if rule.revalidate_on_run and doc and not matches_rule(rule, doc):
		return _finalize(run, rule, row, "Skipped", steps, error="Rule no longer matches")
	status, context = _execute_plan(rule, row, run, doc, steps, snapshot, event)
	_finalize(run, rule, row, status, steps, context=context)


def _execute_plan(rule, row, run, doc, steps, snapshot, event):
	previous_depth = frappe.flags.get("automation_depth", 0)
	frappe.flags.automation_depth = cint(row.depth)
	context = None
	try:
		with _execution_identity(rule, row, doc):
			_ensure_trigger_access(doc)
			context = _context(row, run, rule, doc, event)
			status = _run_plan(steps, rule, doc, context, snapshot, cint(row.resume_from_idx))
		return status, context
	except Exception:
		# Setting up the run (identity, trigger access, alias resolution) failed.
		_append_step(steps, {"step_key": "setup"}, len(steps), "Failed", frappe.get_traceback(), 0)
		return "Failed", context
	finally:
		frappe.flags.automation_depth = previous_depth


def _run_state(rule, row, doc):
	"""Return (run, steps_so_far, actions_snapshot) for a fresh or resumed run."""
	if row.resume_run:
		return _resumed_run_state(row)
	snapshot = [_action_snapshot(action) for action in rule.actions]
	return _create_run(rule, row, snapshot, doc), [], snapshot


def _resumed_run_state(row):
	"""Pick a waiting run back up: same Background Task, its original snapshot and steps."""
	run = frappe.get_doc("Background Task", row.resume_run)
	arguments = frappe.parse_json(run.arguments) if run.arguments else {}
	result = frappe.parse_json(run.result) if run.result else {}
	return run, result.get("steps") or [], arguments.get("actions_snapshot") or []


def _load_target(row):
	if not (row.ref_doctype and row.ref_name):
		return None
	try:
		return frappe.get_doc(row.ref_doctype, row.ref_name)
	except frappe.DoesNotExistError:
		return None


def _create_run(rule, row, snapshot, doc):
	run = frappe.new_doc("Background Task")
	run.update(_task_values(rule, row, snapshot, doc))
	# The referenced doc may legitimately be gone (deleted, or a Doc Deleted trigger); the
	# task must record it regardless, so skip Dynamic Link existence validation.
	run.flags.ignore_links = True
	return run.insert(ignore_permissions=True)


def _task_values(rule, row, snapshot, doc) -> dict:
	return {
		"task_id": frappe.generate_hash(length=20),
		"job_id": row.name,
		"task_name": automation_task_name(rule.name),
		"user": _execution_user(rule, row, doc),
		"method": TASK_METHOD,
		"status": "Running",
		"queue": "default",
		"ref_doctype": row.ref_doctype,
		"ref_docname": row.ref_name,
		"started_at": now(),
		"arguments": frappe.as_json(_task_arguments(rule, row, snapshot)),
		"show_progress_bar": 0,
		"allow_user_cancellation": 0,
		"allow_user_retry": 0,
	}


def _task_arguments(rule, row, snapshot) -> dict:
	return {
		"automation": rule.name,
		"automation_title": rule.title,
		"depth": cint(row.depth),
		"event_payload": frappe.parse_json(row.event_payload) if row.event_payload else {},
		"actions_snapshot": snapshot,
		"relationships": frappe.parse_json(rule.relationships) if rule.relationships else [],
	}


def _action_snapshot(action) -> dict:
	return {
		"idx": cint(action.idx),
		"step_type": action.step_type or "Action",
		"action_type": action.action_type,
		"params": action.params,
		"step_condition": action.step_condition,
		"related_condition": action.related_condition,
		"step_key": action.step_key or f"step_{action.idx}",
		"target": action.target or "trigger",
		"output_alias": action.output_alias,
		"parent_step": cint(action.parent_step),
		"branch": action.branch or "",
	}


def automation_task_name(automation: str) -> str:
	return f"{TASK_NAME_PREFIX}{automation}"


def _context(row, run, rule, doc, event=None) -> dict:
	"""Assemble what steps can read. A resumed run restores the aliases and outputs the first
	leg recorded on the Background Task instead of re-resolving them."""
	arguments = frappe.parse_json(run.arguments) if run.arguments else {}
	result = frappe.parse_json(run.result) if run.result else {}
	return {
		"payload": frappe.parse_json(row.event_payload) if row.event_payload else {},
		"event": event or {},
		"queue_row": row,
		"run": run,
		"rule": rule,
		"trigger_doc": doc,
		"steps": result.get("step_outputs") or {},
		"records": result.get("records") or resolve_relationships(doc, arguments.get("relationships")),
		"branches": result.get("branches") or {},
	}


@contextmanager
def _execution_identity(rule, row, doc):
	# frappe.set_user rebuilds local.session in place, and local.session IS session_obj.data,
	# which the request writes back to tabSessions on the way out. Restoring the user alone
	# would persist an emptied session and log the caller out; the whole session has to go back.
	previous = frappe._dict(frappe.session)
	frappe.set_user(_execution_user(rule, row, doc))
	try:
		yield
	finally:
		frappe.set_user(previous.user)
		frappe.local.session.update(previous)


def _execution_user(rule, row, doc):
	if rule.run_as == "Triggering User":
		return row.triggered_by or rule.owner
	if rule.run_as == "Document Owner" and doc:
		return doc.owner
	return rule.automation_user or "Administrator"


def _ensure_trigger_access(doc):
	if doc:
		doc.check_permission("read")


def _run_plan(steps, rule, doc, context, snapshot, start_idx=0) -> str:
	"""Walk the snapshot once, honouring branch arms and skipping what already ran."""
	registry = get_action_registry()
	taken = context["branches"]
	overall = "Success"
	for pos, step in enumerate(snapshot):
		status, detail, duration = _safe_step_outcome(registry, step, doc, context, pos, start_idx, taken)
		if status is None:
			continue
		entry = _append_step(steps, step, pos, status, detail, duration)
		_update_context(context, step, entry)
		if status == "Waiting":
			return "Waiting"
		if status == "Failed":
			overall = "Partially Failed"
			if rule.stop_on_error:
				return "Failed"
	return overall


def _safe_step_outcome(registry, step, doc, context, pos, start_idx, taken):
	try:
		return _step_outcome(registry, step, doc, context, pos, start_idx, taken)
	except Exception:
		return "Failed", frappe.get_traceback(), 0


def _step_outcome(registry, step, doc, context, pos, start_idx, taken):
	"""Resolve one plan entry. A None status means it is not on this run's path at all."""
	if not _branch_active(step, taken):
		return None, None, None
	step_type = step.get("step_type") or "Action"
	if step_type == "If":
		return _resolve_if(step, doc, context, pos, start_idx, taken)
	if pos < start_idx:
		return None, None, None  # already executed in the leg before the wait
	if not _step_condition_matches(step, doc, context):
		return "Skipped", _skip_detail(step, doc, context), 0
	if step_type == "Wait":
		return _begin_wait(step, context, pos)
	if step_type == "WaitForEvent":
		return _begin_event_wait(step, context, pos)
	return _run_one(registry, step, doc, context, pos)


def _branch_active(step, taken) -> bool:
	"""True when the enclosing If (if any) chose the arm this step sits in."""
	parent = cint(step.get("parent_step"))
	if not parent:
		return True
	arm = taken.get(_branch_key(parent))
	if arm is None:
		return False  # the enclosing If was itself on an arm that wasn't taken
	return (step.get("branch") or "If") == arm


def _branch_key(idx) -> str:
	# Keyed by string: this dict round-trips through the run's JSON result, which has no
	# integer keys, and a resumed leg has to look up what the first one wrote.
	return str(cint(idx))


def _resolve_if(step, doc, context, pos, start_idx, taken):
	"""Pick the arm for an If step, on the leg that first reaches it.

	The arm is run state, not a derivation: the document may have changed during the Wait.
	"""
	key = _branch_key(step.get("idx"))
	if pos < start_idx:
		# Already decided, unless this run parked before arms were recorded.
		if key in taken:
			return None, None, None
		taken[key] = "If" if _step_condition_matches(step, doc, context) else "Else"
		return None, None, None
	taken[key] = arm = "If" if _step_condition_matches(step, doc, context) else "Else"
	return "Success", _("Condition took the {0} branch").format(arm), 0


def _begin_wait(step, context, pos):
	started = time.monotonic()
	seconds = _wait_seconds(_step_params(step))
	schedule_wait(context, seconds, pos + 1)
	return "Waiting", _("Waiting {0} seconds").format(seconds), _ms(started)


def _begin_event_wait(step, context, pos):
	started = time.monotonic()
	subscription = schedule_event_wait(context, _step_params(step), step["step_key"], pos + 1)
	return "Waiting", _("Waiting for {0}").format(subscription.event_name), _ms(started)


def _wait_seconds(params) -> int:
	unit = params.get("unit") or "Minutes"
	return cint(params.get("value")) * WAIT_UNIT_SECONDS.get(unit, 60)


def schedule_wait(context, seconds: int, resume_from_idx: int):
	"""Queue the resume row that picks this run up once the wait elapses."""
	run_after = add_to_date(now(), seconds=seconds)
	frappe.get_doc(resume_row_values(context, run_after, resume_from_idx)).insert(ignore_permissions=True)


def resume_row_values(context, run_after, resume_from_idx) -> dict:
	"""The queue row that continues a parked run at `run_after`.

	dedup_key is NULL whenever resume_run is set, so resume rows never collide with a fresh
	trigger for the same document, or with each other.
	"""
	row = context["queue_row"]
	return {
		"doctype": QUEUE,
		"automation": row.automation,
		"ref_doctype": row.ref_doctype,
		"ref_name": row.ref_name,
		"status": queue_status(run_after),
		"triggered_at": now(),
		"run_after": run_after,
		"depth": cint(row.depth),
		"triggered_by": row.triggered_by,
		"event_payload": row.event_payload,
		"resume_run": context["run"].name,
		"resume_from_idx": resume_from_idx,
	}


def _run_one(registry, step, doc, context, idx):
	started = time.monotonic()
	savepoint = f"auto_step_{idx}"
	handler = registry.get(step.get("action_type"))
	params = _step_params(step)
	for last_attempt in (False, True):
		outcome = _try_action(handler, step, doc, context, params, savepoint, idx, started)
		if outcome[0] != "Retry":
			return outcome
		if last_attempt:
			return "Failed", outcome[1], outcome[2]
		if doc:
			doc.reload()


def _try_action(handler, step, doc, context, params, savepoint, idx, started):
	frappe.db.savepoint(savepoint)
	messages_before = len(frappe.local.message_log)
	try:
		target = _target_doc(step, doc, context, permission_type="write")
		if not handler:
			raise ValueError(f"Unknown action type: {step.get('action_type')}")
		handler.validate(params, target.doctype if target else None)
		return "Success", handler.execute(target, params, context), _ms(started)
	except StopAutomation as error:
		schedule_wait(context, error.resume_after, idx + 1)
		return "Waiting", str(error) or _("Automation paused"), _ms(started)
	except frappe.TimestampMismatchError:
		frappe.db.rollback(save_point=savepoint)
		return "Retry", frappe.get_traceback(), _ms(started)
	except Exception as error:
		frappe.db.rollback(save_point=savepoint)
		return "Failed", _failure_detail(error, messages_before), _ms(started)


def _skip_detail(step, doc, context) -> dict:
	"""Why a gated step was passed over: the condition source, and the values it read."""
	condition = step.get("step_condition") or ""
	target = _target_doc(step, doc, context, permission_type="read") if condition else None
	return {
		"note": True,
		"detail": _("Step condition did not match"),
		"condition": condition or step.get("related_condition") or "",
		"condition_values": condition_values(condition, {"doc": doc, "target": target}),
	}


def _failure_detail(error, messages_before) -> dict:
	"""What the step failed with: the traceback, plus anything the action threw as a message."""
	traceback = frappe.get_traceback()
	return {
		"note": True,
		"detail": traceback,
		"traceback": traceback,
		"message": _thrown_message(error, messages_before),
		"exception": f"{type(error).__module__}.{type(error).__name__}",
	}


def _thrown_message(error, messages_before) -> str:
	thrown = frappe.local.message_log[messages_before:]
	messages = [message.get("message") for message in thrown if message.get("message")]
	return "\n".join(messages) if messages else str(error)


def _step_params(step) -> dict:
	params = step.get("params")
	return (frappe.parse_json(params) if isinstance(params, str) else params) or {}


def _step_condition_matches(step, doc, context) -> bool:
	if not evaluate_related_condition(step.get("related_condition"), context):
		return False
	condition = step.get("step_condition")
	if not condition:
		return True
	target = _target_doc(step, doc, context, permission_type="read")
	return bool(frappe.safe_eval(condition, None, {"doc": doc, "target": target, "context": context}))


def _append_step(steps, step, idx, status, detail, duration):
	note = detail if isinstance(detail, dict) and detail.get("note") else {}
	detail, output = (note["detail"], None) if note else _action_result(detail)
	entry = {
		"step_idx": idx,
		"step_key": step.get("step_key") or f"step_{idx + 1}",
		"action_type": step.get("action_type") or step.get("step_type") or "Action",
		"status": status,
		"detail": (detail or "")[:5000],
		"message": _trim(note.get("message")),
		"exception": note.get("exception"),
		"traceback": _trim(note.get("traceback")),
		"condition": note.get("condition"),
		"condition_values": note.get("condition_values"),
		"output": output,
		"duration_ms": duration,
	}
	steps.append(entry)
	return entry


def _trim(value):
	return value[:5000] if value else None


def _target_doc(step, trigger_doc, context, permission_type=None):
	target = step.get("target") or "trigger"
	if target == "trigger":
		if trigger_doc and permission_type:
			trigger_doc.check_permission(permission_type)
		return trigger_doc
	return load_record(context["records"].get(target), permission_type=permission_type)


def _update_context(context, step, entry):
	"""Publish a finished step's output so later steps and Jinja can read it."""
	output = entry.get("output") or {}
	if not _within_output_limit(output):
		# The action already ran, so oversized output is dropped rather than failing the run.
		entry["output"] = output = {"truncated": True}
	context["steps"][entry["step_key"]] = output
	alias = step.get("output_alias")
	if alias and output.get("destination_reference"):
		context["records"][alias] = output["destination_reference"]


def _within_output_limit(output) -> bool:
	return len(frappe.as_json(output).encode()) <= settings.get("step_output_limit")


def _action_result(result):
	if not isinstance(result, dict):
		return result, None
	detail = result.get("detail") or result.get("destination_reference") or _("Action completed")
	return str(detail), result


def _ms(started) -> int:
	return int((time.monotonic() - started) * 1000)


def _finalize(run, rule, row, status, steps, error=None, context=None):
	error_summary = error or _error_summary(status, steps)
	run.update(_run_values(rule, row, status, steps, error_summary, context))
	# The target may have been deleted since the run started (notably across a Wait, or on a
	# Doc Deleted trigger); the task must still record its outcome, so skip link validation.
	run.flags.ignore_links = True
	run.save(ignore_permissions=True)
	_settle_queue_row(row, status)

	# Neither of the things below is in the transaction a trial rolls back: the breaker counter
	# lives in Redis, and a realtime event has already left.
	if frappe.flags.get("in_automation_trial"):
		return

	if status == "Failed":
		_record_failure(rule)
	elif status == "Success":
		_reset_failures(rule)

	_publish_update(run, rule, status)


def _publish_update(run, rule, status):
	frappe.publish_realtime(
		"automation_run_update",
		{"automation": rule.name, "run": run.name, "status": status},
		doctype=run.ref_doctype,
		docname=run.ref_docname,
	)


def _run_values(rule, row, status, steps, error_summary, context=None) -> dict:
	values = {
		"result": frappe.as_json(_run_result(rule, row, status, steps, error_summary, context)),
		"exception": _first_error_detail(steps) if status == "Failed" else None,
	}
	if status == "Waiting":
		# Background Task has no paused state, and the resume row finishes this same task.
		return {**values, "status": "Running"}
	return {
		**values,
		"status": "Failed" if status == "Failed" else "Completed",
		"ended_at": now(),
		"progress": 100,
	}


def _settle_queue_row(row, status):
	# Completed and Waiting rows are dropped; Failed and Skipped are kept for the purge sweep.
	# Plain DELETE rather than frappe.delete_doc, which would archive a Deleted Document copy of
	# every queue row this site ever ran.
	if status in ("Success", "Partially Failed", "Waiting"):
		frappe.db.delete(QUEUE, {"name": row.name})
	else:
		frappe.db.set_value(QUEUE, row.name, "status", status, update_modified=False)


def _run_result(rule, row, status, steps, error_summary, context=None) -> dict:
	result = {
		"automation": rule.name,
		"automation_title": rule.title,
		"automation_status": status,
		"depth": cint(row.depth),
		"error_summary": error_summary,
		"steps": steps,
	}
	if context:
		result.update(
			{
				"step_outputs": context["steps"],
				"records": context["records"],
				"branches": context["branches"],
			}
		)
	return result


def _error_summary(status, steps) -> str | None:
	"""One line for the run list. The app's own thrown message beats a traceback tail."""
	if status not in ("Failed", "Partially Failed"):
		return None
	failed = next((step for step in steps if step["status"] == "Failed"), None)
	message = (failed or {}).get("message")
	if message:
		return message.splitlines()[0][:140]
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
	threshold = settings.get("failure_threshold")
	if frappe.cache.incr(_failure_key(rule.name)) >= threshold:
		_trip_breaker(rule, threshold)


def _reset_failures(rule):
	frappe.cache.delete(_failure_key(rule.name))


def _trip_breaker(rule, threshold):
	reason = _("Auto-disabled after {0} consecutive failures").format(threshold)
	frappe.db.set_value(
		"Automation Flow", rule.name, {"enabled": 0, "disabled_reason": reason}, update_modified=False
	)
	# Drop the orphaned backlog in one UPDATE, the rule won't run again.
	frappe.db.set_value(
		QUEUE,
		{"automation": rule.name, "status": ("in", WAITING_STATES)},
		"status",
		"Skipped",
		update_modified=False,
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
