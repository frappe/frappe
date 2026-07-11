# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Hot path: match document lifecycle events against cached rules and enqueue the outbox.

Called once from Document.run_method, adjacent to run_notifications / run_webhooks /
run_server_script_for_doc_event. Nothing here issues a query before the cached map check,
and queue_trigger runs inside the caller's save transaction; a single deduplicated drainer
job is kicked after commit.
"""

import frappe
from frappe.automation_engine.registry import get_automations_for
from frappe.utils.data import evaluate_filters

# Document lifecycle method -> trigger type. A save fires both on_update and on_change,
# so "Doc Updated" and "Field Value Changed" rules stay on distinct methods (no double-queue).
METHOD_TRIGGER = {
	"after_insert": "Doc Created",
	"on_update": "Doc Updated",
	"on_change": "Field Value Changed",
	"on_submit": "Doc Submitted",
	"on_cancel": "Doc Cancelled",
	"on_trash": "Doc Deleted",
}

DEFAULT_MAX_DEPTH = 3


def run_automations(doc, method):
	"""Entry point wired into Document.run_method."""
	trigger_type = METHOD_TRIGGER.get(method)
	if not trigger_type or not _should_dispatch(doc):
		return

	# on_update also fires during insert; the insert path is owned by "Doc Created".
	if trigger_type == "Doc Updated" and doc.flags.get("in_insert"):
		return

	rules = get_automations_for(doc.doctype)
	if not rules:
		return

	depth = frappe.flags.get("automation_depth", 0) + 1
	kicked = False
	for rule in rules:
		if rule.trigger_type == trigger_type and _matches(rule, doc):
			queue_trigger(rule.name, doc.doctype, doc.name, depth=depth)
			kicked = True

	if kicked:
		frappe.db.after_commit.add(kick_drainer)


def _should_dispatch(doc) -> bool:
	flags = frappe.flags
	if flags.get("skip_automations") or flags.in_install or flags.in_patch or flags.in_migrate:
		return False
	if frappe.conf.get("automation_disabled"):
		return False
	max_depth = frappe.conf.get("automation_max_depth") or DEFAULT_MAX_DEPTH
	return flags.get("automation_depth", 0) < max_depth


def _matches(rule, doc) -> bool:
	if rule.trigger_type == "Field Value Changed" and not _field_changed(rule, doc):
		return False
	if rule.filters and not evaluate_filters(doc, frappe.parse_json(rule.filters)):
		return False
	if rule.condition and not frappe.safe_eval(rule.condition, None, {"doc": doc}):
		return False
	return True


def _field_changed(rule, doc) -> bool:
	before = doc.get_doc_before_save()
	if not before:
		return False
	old, new = before.get(rule.trigger_field), doc.get(rule.trigger_field)
	if old == new:
		return False
	if rule.from_value not in (None, "") and str(old) != str(rule.from_value):
		return False
	if rule.to_value not in (None, "") and str(new) != str(rule.to_value):
		return False
	return True


def queue_trigger(automation, doctype, docname, run_after=None, payload=None, depth=0):
	"""Upsert a Pending outbox row inside the caller's transaction (dedup on rerun)."""
	existing = frappe.db.get_value(
		"Automation Trigger Queue",
		{
			"automation": automation,
			"ref_doctype": doctype,
			"ref_name": docname,
			"status": "Pending",
			"resume_run": ("is", "not set"),
		},
		"name",
	)
	if existing:
		frappe.db.set_value(
			"Automation Trigger Queue",
			existing,
			{"triggered_at": frappe.utils.now(), "run_after": run_after},
			update_modified=False,
		)
		return existing

	row = frappe.new_doc("Automation Trigger Queue")
	row.update(
		{
			"automation": automation,
			"ref_doctype": doctype,
			"ref_name": docname,
			"status": "Pending",
			"triggered_at": frappe.utils.now(),
			"run_after": run_after,
			"event_payload": frappe.as_json(payload) if payload else None,
			"depth": depth,
		}
	)
	row.insert(ignore_permissions=True)
	return row.name


def kick_drainer():
	"""Enqueue a single deduplicated drain job (registered via after_commit)."""
	frappe.enqueue(
		"frappe.automation_engine.drainer.drain",
		queue="default",
		job_id=f"automation_drain::{frappe.local.site}",
		deduplicate=True,
	)
