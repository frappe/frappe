# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from frappe.model.document import Document

DOC_EVENTS = frozenset({"after_insert", "on_update", "on_submit", "on_cancel", "on_trash"})


def dispatch(doc: Document, method: str | None = None) -> None:
	"""doc_events hook: enqueue any matching DocType Event triggers."""
	if method not in DOC_EVENTS:
		return
	if doc.doctype in {"Flow Run", "Flow Trigger", "Flow Agent", "Flow Tool", "Flow Model"}:
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_install_db:
		return

	triggers = _doctype_triggers(doc.doctype, method)

	for trigger in triggers:
		if trigger.condition and not _passes_condition(trigger, doc):
			continue
		frappe.enqueue(
			"flow.triggers.fire",
			enqueue_after_commit=True,
			trigger=trigger.name,
			target_doctype=doc.doctype,
			target_name=doc.name,
		)


def dispatch_scheduled() -> None:
	"""Scheduler hook: fire any Scheduled triggers whose cron is due."""
	from croniter import CroniterBadCronError, croniter

	now = frappe.utils.now_datetime()
	triggers = frappe.get_all(
		"Flow Trigger",
		filters={"event": "Scheduled", "enabled": 1},
		fields=["name", "cron_expression", "last_fired_at", "creation"],
	)
	for t in triggers:
		# Anchor on last fire; fall back to creation so the first run isn't deferred forever.
		anchor = frappe.utils.get_datetime(t.last_fired_at or t.creation)
		try:
			nxt = croniter(t.cron_expression, anchor).get_next(datetime)
		except (CroniterBadCronError, ValueError):
			frappe.log_error(title=f"Flow Trigger cron parse failed: {t.name}")
			continue
		if nxt <= now:
			frappe.db.set_value("Flow Trigger", t.name, "last_fired_at", now, update_modified=False)
			frappe.enqueue("flow.triggers.fire", trigger=t.name)


def fire(
	trigger: str,
	target_doctype: str | None = None,
	target_name: str | None = None,
) -> str | None:
	"""Worker: render the prompt and run the agent. Returns the Flow Run name, or None if skipped."""
	t = frappe.get_doc("Flow Trigger", trigger)
	if not t.enabled:
		return None

	# A trigger runs as its configured `run_as` user (falling back to the owner)
	original_user = frappe.session.user
	frappe.set_user(t.run_as or t.owner)
	try:
		doc = None
		if target_doctype and target_name:
			try:
				doc = frappe.get_doc(target_doctype, target_name)
			except frappe.DoesNotExistError:
				return None
			if t.condition and not _eval_condition(t.condition, doc):
				return None

		prompt = frappe.render_template(t.prompt_template, {"doc": doc, "now": frappe.utils.now_datetime()})
		agent_doc = frappe.get_doc("Flow Agent", t.agent)
		run = agent_doc.run(
			prompt,
			source="Trigger",
			trigger=t.name,
			reference_doctype=target_doctype if doc else None,
			reference_name=target_name if doc else None,
			auto_approve=bool(t.auto_approve),
		)
		return run.name
	finally:
		frappe.set_user(original_user)


def _doctype_triggers(target_doctype: str, doc_event: str) -> list:
	return frappe.get_all(
		"Flow Trigger",
		filters={
			"event": "DocType Event",
			"target_doctype": target_doctype,
			"doc_event": doc_event,
			"enabled": 1,
		},
		fields=["name", "condition", "run_as", "owner"],
	)


def _passes_condition(trigger, doc: Document) -> bool:
	"""Evaluate the pre-enqueue condition as the trigger's run identity (matching fire),
	so a permission-sensitive condition doesn't silently under-fire for the low-privilege
	user whose action triggered it."""
	original_user = frappe.session.user
	frappe.set_user(trigger.run_as or trigger.owner)
	try:
		return _eval_condition(trigger.condition, doc)
	finally:
		frappe.set_user(original_user)


def _eval_condition(condition: str, doc: Document) -> bool:
	from frappe.utils.safe_exec import get_safe_globals

	from flow.utils.conditions import evaluate_condition

	context = {"doc": doc, "utils": get_safe_globals().get("frappe").get("utils")}
	try:
		return evaluate_condition(condition, context)
	except Exception:
		frappe.log_error(title="Flow Trigger condition eval failed")
		return False
