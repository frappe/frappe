# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine import settings
from frappe.automation_engine.queue import QUEUE, WAITING_STATES, queue_status
from frappe.automation_engine.registry import get_automations_for
from frappe.utils import cint, cstr, now
from frappe.utils.data import evaluate_filters

METHOD_TRIGGER = {
	"after_insert": "Doc Created",
	"on_update": "Doc Updated",
	"on_change": "Field Value Changed",
	"on_submit": "Doc Submitted",
	"on_cancel": "Doc Cancelled",
	"on_trash": "Doc Deleted",
}


def run_automations(doc, method):
	"""Entry point wired into Document.run_method."""
	trigger_type = METHOD_TRIGGER.get(method)
	if not trigger_type or not _dispatch_allowed():
		return

	# on_update also fires during insert
	if trigger_type == "Doc Updated" and doc.flags.get("in_insert"):
		return

	rules = get_automations_for(doc.doctype)
	if not rules:
		return

	matched = [r for r in rules if r.trigger_type == trigger_type and matches_rule(r, doc)]
	if not matched:
		return

	# Enforce recursion depth only once we know there's real work to do. Checking earlier
	# would log a refusal for every unrelated save (Run logs, ToDos, Notification Logs)
	depth = cint(frappe.flags.get("automation_depth")) + 1
	max_depth = settings.get("max_depth")
	if depth > max_depth:
		_log_depth_refusal(doc, max_depth)
		return

	for rule in matched:
		queue_trigger(rule.name, doc.doctype, doc.name, depth=depth)
	frappe.db.after_commit.add(kick_drainer)


def _dispatch_allowed() -> bool:
	flags = frappe.flags
	if not settings.is_enabled():
		return False
	return not (flags.in_install or flags.in_patch or flags.in_migrate)


def _log_depth_refusal(doc, max_depth):
	previous = frappe.flags.get("skip_automations")
	frappe.flags.skip_automations = True
	try:
		frappe.log_error(
			title="Automation Flow depth limit reached",
			message=f"Skipped automations for {doc.doctype} {doc.name} at depth {max_depth}",
		)
	finally:
		frappe.flags.skip_automations = previous


def matches_rule(rule, doc) -> bool:
	"""Whether `doc` satisfies the rule's trigger field, filters and condition."""
	try:
		if rule.trigger_type == "Field Value Changed" and not _field_changed(rule, doc):
			return False
		if rule.filters and not evaluate_filters(doc, frappe.parse_json(rule.filters)):
			return False
		return not rule.condition or bool(frappe.safe_eval(rule.condition, None, {"doc": doc}))
	except Exception:
		frappe.log_error(
			title=f"Automation Flow match failed: {rule.name}",
			message=frappe.get_traceback(),
		)
		return False


def _field_changed(rule, doc) -> bool:
	before = doc.get_doc_before_save()
	if not before:
		return False
	old, new = before.get(rule.trigger_field), doc.get(rule.trigger_field)
	if old == new:
		return False
	if rule.from_value not in (None, "") and cstr(old) != cstr(rule.from_value):
		return False
	if rule.to_value not in (None, "") and cstr(new) != cstr(rule.to_value):
		return False
	return True


def queue_trigger(automation, doctype, docname, run_after=None, payload=None, depth=0):
	"""Insert the waiting queue row for this automation and document, or refresh the existing one.

	The `dedup_key` unique index is the real guard; the lookup below only avoids the failed insert.
	"""
	existing = _pending_row(automation, doctype, docname)
	if existing:
		return _touch_row(existing, run_after)

	row = frappe.new_doc(QUEUE)
	row.update(
		{
			"automation": automation,
			"ref_doctype": doctype,
			"ref_name": docname,
			"status": queue_status(run_after),
			"triggered_at": now(),
			"triggered_by": frappe.session.user,
			"run_after": run_after,
			"event_payload": frappe.as_json(payload) if payload else None,
			"depth": depth,
		}
	)
	try:
		row.insert(ignore_permissions=True)
		return row.name
	except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
		existing = _pending_row(automation, doctype, docname)
		return _touch_row(existing, run_after) if existing else None


def _pending_row(automation, doctype, docname):
	return frappe.db.get_value(
		QUEUE,
		{
			"automation": automation,
			"ref_doctype": doctype,
			"ref_name": docname,
			"status": ("in", WAITING_STATES),
			"resume_run": ("is", "not set"),
		},
		"name",
	)


def _touch_row(name, run_after):
	frappe.db.set_value(
		QUEUE,
		name,
		{
			"triggered_at": now(),
			"run_after": run_after,
			"status": queue_status(run_after),
		},
		update_modified=False,
	)
	return name


def kick_drainer():
	"""Enqueue a single deduplicated drain job (registered via after_commit)."""
	frappe.enqueue(
		"frappe.automation_engine.drainer.drain",
		queue="default",
		job_id=f"automation_drain::{frappe.local.site}",
		deduplicate=True,
	)
