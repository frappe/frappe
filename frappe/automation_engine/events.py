# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import frappe
from frappe import _
from frappe.automation_engine import settings
from frappe.automation_engine.dispatch import kick_drainer, matches_rule, queue_trigger
from frappe.automation_engine.queue import QUEUE
from frappe.automation_engine.registry import get_custom_event_map
from frappe.utils import add_to_date, cint, get_datetime, now, now_datetime

SUBSCRIPTION = "Automation Event Subscription"
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
	# Deferred: runner imports this module at load time.
	from frappe.automation_engine.runner import resume_row_values

	validate_wait_params(params)
	correlation = _render(params["correlation_key"], context)
	if not correlation:
		frappe.throw(_("Wait for Event correlation key rendered empty"))

	expires_at = add_to_date(now(), seconds=_timeout_seconds(params))
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


def registered_events(doctype: str | None = None) -> list[dict]:
	"""Events apps declared via the `automation_events` hook, with their builder metadata.

	Pass `doctype` to keep only the events that can be *about* that DocType, so the builder
	can offer them as triggers on it.
	"""
	options = [_event_option(name, schema) for name, schema in sorted(_registered_events().items())]
	if not doctype:
		return options
	return [option for option in options if doctype in option["subject_doctypes"]]


def _event_option(name, schema) -> dict:
	schema = schema if isinstance(schema, dict) else {}
	return {
		"value": name,
		"label": schema.get("label") or _prettify(name),
		"description": schema.get("description") or "",
		"correlation_options": schema.get("correlation_options") or [],
		"subject_doctypes": _subject_doctypes(schema.get("subject")),
	}


def _subject_doctypes(subject) -> list[str]:
	"""The DocTypes an event's subject can be, for a builder that must decide statically."""
	if not isinstance(subject, dict):
		return []
	if subject.get("doctype"):
		return [subject["doctype"]]
	return list(subject.get("doctypes") or [])


def event_subject(event: str, payload: dict) -> dict | None:
	"""Resolve the record an event is about, from the keys its schema declares.

	Events without a `subject` return None, and keep matching against the emitted document.
	"""
	subject = (_registered_events().get(event) or {}).get("subject")
	if not isinstance(subject, dict):
		return None
	doctype = subject.get("doctype") or (payload or {}).get(subject.get("doctype_key") or "")
	name = (payload or {}).get(subject.get("name_key") or "")
	if not doctype or not name:
		return None
	allowed = _subject_doctypes(subject)
	if allowed and doctype not in allowed:
		return None
	return {"doctype": doctype, "name": name}


def _prettify(name) -> str:
	return name.split(".")[-1].replace("_", " ").capitalize()


def validate_event(event):
	if event in _registered_events():
		return
	if settings.get("allow_unregistered_events"):
		return
	frappe.throw(_("Unregistered automation event: {0}").format(event))


def validate_wait_params(params):
	validate_event(params.get("event_name"))
	if not params.get("correlation_key"):
		frappe.throw(_("Wait for Event requires a correlation key"))
	if not cint(params.get("timeout_value")):
		frappe.throw(_("Wait for Event requires a timeout"))
	if params.get("timeout_unit") not in TIMEOUT_UNITS:
		frappe.throw(_("Wait for Event timeout unit must be one of {0}").format(", ".join(TIMEOUT_UNITS)))


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
	"""Queue every flow this event matches, against the record the event is about.

	An event that declares a subject runs its flows on that record rather than on the document
	the emitter happened to hold, so "we emailed the prospect" is a Lead trigger, not a
	Communication one.
	"""
	queued = 0
	occurrence = frappe.generate_hash(length=20)
	subject_doc = _subject_document(event, payload)
	for rule in get_custom_event_map().get(event, []):
		target = subject_doc if subject_doc and rule.document_type == subject_doc.doctype else doc
		if rule.document_type and (not target or target.doctype != rule.document_type):
			continue
		if target and not matches_rule(rule, target):
			continue
		queue_trigger(
			rule.name,
			target.doctype if target else None,
			target.name if target else occurrence,
			payload=payload,
		)
		queued += 1
	return queued


def _subject_document(event, payload):
	"""Load the event's subject, or None when it declares none or it no longer exists."""
	reference = event_subject(event, payload)
	if not reference:
		return None
	if not frappe.db.exists(reference["doctype"], reference["name"]):
		return None
	return frappe.get_doc(reference["doctype"], reference["name"])


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
	matched = get_datetime(subscription.expires_at) > now_datetime()
	subscription.db_set(
		{
			"status": "Matched" if matched else "Timed Out",
			"event_payload": frappe.as_json(payload) if matched else None,
		},
		update_modified=False,
	)
	# Bring the resume row forward - it was scheduled for the (now irrelevant) timeout.
	frappe.db.set_value(QUEUE, subscription.resume_queue, "run_after", now(), update_modified=False)
	return 1 if matched else 0


def _lock_subscription(name):
	table = frappe.qb.DocType(SUBSCRIPTION)
	frappe.qb.from_(table).select(table.name).where(table.name == name).for_update().run()
	return frappe.get_doc(SUBSCRIPTION, name)


def _timeout_seconds(params) -> int:
	return cint(params["timeout_value"]) * TIMEOUT_UNITS[params["timeout_unit"]]


def _render(value, context):
	if not isinstance(value, str) or "{{" not in value:
		return value
	# nosemgrep: the template is the flow's correlation key, authored with the Wait step.
	return frappe.render_template(
		value,
		{
			"doc": context.get("trigger_doc"),
			"context": context,
			"payload": context.get("payload") or {},
		},
	)


def _validate_payload_size(payload):
	if len(frappe.as_json(payload).encode()) > settings.get("event_payload_limit"):
		frappe.throw(_("Automation event payload is too large"))
