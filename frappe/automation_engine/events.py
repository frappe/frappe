# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import frappe
from frappe import _
from frappe.automation_engine.dispatch import kick_drainer, matches_rule, queue_trigger
from frappe.automation_engine.registry import get_custom_event_map

SUBSCRIPTION = "Automation Event Subscription"
QUEUE = "Automation Trigger Queue"
TIMEOUT_UNITS = {"Seconds": 1, "Minutes": 60, "Hours": 3600, "Days": 86400}


def emit(event, doc=None, payload=None, correlation_key=None) -> dict:
	"""Queue matching Custom Event flows and claim correlated waits. Safe to call twice."""
	validate_event(event)
	payload = {**(payload or {}), "event_name": event}
	_validate_payload_size(payload)
	queued = _queue_event_flows(event, doc, payload)
	resumed = _claim_subscriptions(event, correlation_key, payload)
	if queued or resumed:
		frappe.db.after_commit.add(kick_drainer)
	return {"queued": queued, "resumed": resumed}


def schedule_event_wait(context, params, step_key, resume_from_idx):
	"""Park the run: insert the subscription and the resume row due at the timeout."""
	from frappe.automation_engine.runner import resume_row_values

	validate_wait_params(params)
	correlation = _render(params["correlation_key"], context)
	if not correlation:
		frappe.throw(_("Wait for Event correlation key rendered empty"))

	expires_at = frappe.utils.add_to_date(frappe.utils.now(), seconds=_timeout_seconds(params))
	queue = frappe.get_doc(resume_row_values(context, expires_at, resume_from_idx)).insert(
		ignore_permissions=True
	)
	return frappe.get_doc(
		{
			"doctype": SUBSCRIPTION,
			"event_name": params["event_name"],
			"correlation_key": correlation,
			"run": context["run"].name,
			"step_key": step_key,
			"resume_queue": queue.name,
			"expires_at": expires_at,
			"status": "Waiting",
		}
	).insert(ignore_permissions=True)


def get_wait_outcome(row) -> dict | None:
	"""Settle the wait this resume row belongs to, and report how it ended.

	Called at the top of every run: a row with no subscription behind it isn't an event wait.
	If nothing has claimed the subscription by now, this resume row is the timeout.
	"""
	name = frappe.db.get_value(SUBSCRIPTION, {"resume_queue": row.name}, "name")
	if not name:
		return None
	subscription = _lock_subscription(name)
	if subscription.status == "Waiting":
		subscription.db_set("status", "Timed Out", update_modified=False)
	return {
		"outcome": subscription.status,
		"event_name": subscription.event_name,
		"payload": frappe.parse_json(subscription.event_payload) if subscription.event_payload else {},
	}


def registered_events() -> list[dict]:
	"""Events apps declared via the `automation_events` hook, with their builder metadata.

	An app may register a bare name or a `{name: schema}` map. The schema is what lets a
	builder offer a readable label and ready-made correlation keys instead of asking someone
	to hand-write a Jinja expression.
	"""
	return [_event_option(name, schema) for name, schema in sorted(_registered_events().items())]


def _event_option(name, schema) -> dict:
	schema = schema if isinstance(schema, dict) else {}
	return {
		"value": name,
		"label": schema.get("label") or _prettify(name),
		"description": schema.get("description") or "",
		"correlation_options": schema.get("correlation_options") or [],
	}


def _prettify(name) -> str:
	return name.split(".")[-1].replace("_", " ").capitalize()


def validate_event(event):
	if event in _registered_event_names():
		return
	if frappe.conf.get("allow_unregistered_automation_events"):
		return
	frappe.throw(_("Unregistered automation event: {0}").format(event))


def validate_wait_params(params):
	validate_event(params.get("event_name"))
	if not params.get("correlation_key"):
		frappe.throw(_("Wait for Event requires a correlation key"))
	if not frappe.utils.cint(params.get("timeout_value")):
		frappe.throw(_("Wait for Event requires a timeout"))
	if params.get("timeout_unit") not in TIMEOUT_UNITS:
		frappe.throw(_("Wait for Event timeout unit must be one of {0}").format(", ".join(TIMEOUT_UNITS)))


def _registered_event_names() -> set[str]:
	return set(_registered_events())


def _registered_events() -> dict:
	"""{name: schema}. Apps may register a bare name or a {name: schema} map."""
	events = {}
	for value in frappe.get_hooks("automation_events"):
		if isinstance(value, str):
			events.setdefault(value, {})
		else:
			events.update(value)
	return events


def _queue_event_flows(event, doc, payload) -> int:
	queued = 0
	occurrence = frappe.generate_hash(length=20)
	for rule in get_custom_event_map().get(event, []):
		if rule.document_type and (not doc or doc.doctype != rule.document_type):
			continue
		if doc and not matches_rule(rule, doc):
			continue
		queue_trigger(
			rule.name, doc.doctype if doc else None, doc.name if doc else occurrence, payload=payload
		)
		queued += 1
	return queued


def _claim_subscriptions(event, correlation_key, payload) -> int:
	if not correlation_key:
		return 0
	names = frappe.get_all(
		SUBSCRIPTION,
		filters={"event_name": event, "correlation_key": correlation_key, "status": "Waiting"},
		pluck="name",
	)
	return sum(_claim_subscription(name, payload) for name in names)


def _claim_subscription(name, payload) -> int:
	"""Return 1 when this emission is what resumed the run."""
	subscription = _lock_subscription(name)
	if subscription.status != "Waiting":
		return 0  # the timeout, or a concurrent emission, already claimed it
	matched = frappe.utils.get_datetime(subscription.expires_at) > frappe.utils.now_datetime()
	subscription.db_set(
		{
			"status": "Matched" if matched else "Timed Out",
			"event_payload": frappe.as_json(payload) if matched else None,
		},
		update_modified=False,
	)
	# Bring the resume row forward - it was scheduled for the (now irrelevant) timeout.
	frappe.db.set_value(
		QUEUE, subscription.resume_queue, "run_after", frappe.utils.now(), update_modified=False
	)
	return 1 if matched else 0


def _lock_subscription(name):
	table = frappe.qb.DocType(SUBSCRIPTION)
	frappe.qb.from_(table).select(table.name).where(table.name == name).for_update().run()
	return frappe.get_doc(SUBSCRIPTION, name)


def _timeout_seconds(params) -> int:
	return frappe.utils.cint(params["timeout_value"]) * TIMEOUT_UNITS[params["timeout_unit"]]


def _render(value, context):
	if not isinstance(value, str) or "{{" not in value:
		return value
	return frappe.render_template(
		value,
		{
			"doc": context.get("trigger_doc"),
			"context": context,
			"payload": context.get("payload") or {},
		},
	)


def _validate_payload_size(payload):
	limit = frappe.conf.get("automation_event_payload_limit") or 65536
	if len(frappe.as_json(payload).encode()) > limit:
		frappe.throw(_("Automation event payload is too large"))
