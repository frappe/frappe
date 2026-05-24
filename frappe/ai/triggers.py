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
	if doc.doctype in {"AI Run", "AI Trigger", "AI Agent", "AI Tool", "AI Model"}:
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_install_db:
		return

	triggers = _doctype_triggers(doc.doctype, method)

	for trigger in triggers:
		if trigger.condition and not _eval_condition(trigger.condition, doc):
			continue
		frappe.enqueue(
			"frappe.ai.triggers.fire",
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
		"AI Trigger",
		filters={"event": "Scheduled", "enabled": 1},
		fields=["name", "cron_expression", "last_fired_at"],
	)
	for t in triggers:
		try:
			anchor = t.last_fired_at or croniter(t.cron_expression, now).get_prev(datetime)
			nxt = croniter(t.cron_expression, anchor).get_next(datetime)
		except (CroniterBadCronError, ValueError):
			frappe.log_error(title=f"AI Trigger cron parse failed: {t.name}")
			continue
		if nxt <= now:
			frappe.db.set_value("AI Trigger", t.name, "last_fired_at", now, update_modified=False)
			frappe.enqueue("frappe.ai.triggers.fire", trigger=t.name)


def fire(
	trigger: str,
	target_doctype: str | None = None,
	target_name: str | None = None,
) -> str | None:
	"""Worker: render the prompt and run the agent. Returns the AI Run name, or None if skipped."""
	t = frappe.get_doc("AI Trigger", trigger)
	if not t.enabled:
		return None

	doc = None
	if target_doctype and target_name:
		try:
			doc = frappe.get_doc(target_doctype, target_name)
		except frappe.DoesNotExistError:
			return None
		if t.condition and not _eval_condition(t.condition, doc):
			return None

	prompt = frappe.render_template(
		t.prompt_template, {"doc": doc, "now": frappe.utils.now_datetime()}
	)
	agent_doc = frappe.get_doc("AI Agent", t.agent)
	run = agent_doc.run(prompt, source="Trigger", trigger=t.name)
	return run.name


def _doctype_triggers(target_doctype: str, doc_event: str) -> list:
	return frappe.get_all(
		"AI Trigger",
		filters={
			"event": "DocType Event",
			"target_doctype": target_doctype,
			"doc_event": doc_event,
			"enabled": 1,
		},
		fields=["name", "condition"],
	)


def _eval_condition(condition: str, doc: Document) -> bool:
	from frappe.integrations.doctype.webhook.webhook import get_context

	try:
		return bool(frappe.safe_eval(condition, eval_locals=get_context(doc)))
	except Exception:
		frappe.log_error(title="AI Trigger condition eval failed")
		return False
