# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine import settings
from frappe.automation_engine.queue import DRAIN_QUEUE, QUEUE, WAITING_STATES, queue_status
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
	# Flags first, because they are free and settings is not: reading the Single imports its
	# controller, and during install the DocType row does not exist yet, so the import resolves
	# to the wrong module and raises. Nothing should dispatch during install/patch/migrate
	# anyway, so the database is never touched on those paths.
	if flags.in_install or flags.in_patch or flags.in_migrate:
		return False
	return settings.is_enabled()


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
		return _touch_row(existing, run_after, payload, depth)

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
		return _touch_row(existing, run_after, payload, depth) if existing else None


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
		["name", "depth"],
		as_dict=True,
	)


def _touch_row(row, run_after, payload=None, depth=0):
	"""Fold a repeat trigger into the waiting row.

	One row stands in for every trigger that collapsed onto it, and the run it produces reads the
	document as it is when the drainer gets there - so the row has to carry the newest trigger's
	context, not the first one's. Keeping the original caller would run a later user's change under
	an earlier user's identity.

	Depth is the exception: it guards recursion, so the deepest of the collapsed triggers wins
	rather than the newest. The payload is only replaced when the new trigger actually carries one,
	so a plain doc event folding onto an emitted one cannot erase it.
	"""
	values = {
		"triggered_at": now(),
		"triggered_by": frappe.session.user,
		"run_after": run_after,
		"status": queue_status(run_after),
		"depth": max(cint(row.depth), cint(depth)),
	}
	if payload:
		values["event_payload"] = frappe.as_json(payload)
	frappe.db.set_value(QUEUE, row.name, values, update_modified=False)
	return row.name


def kick_drainer():
	"""Enqueue a single deduplicated drain job (registered via after_commit)."""
	frappe.enqueue(
		"frappe.automation_engine.drainer.drain",
		queue=DRAIN_QUEUE,
		job_id=f"automation_drain::{frappe.local.site}",
		deduplicate=True,
	)
