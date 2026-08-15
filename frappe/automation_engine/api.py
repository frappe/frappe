# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


from contextlib import contextmanager

import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationParamError, get_action, get_action_registry
from frappe.automation_engine.dispatch import kick_drainer, queue_trigger
from frappe.automation_engine.events import registered_events
from frappe.automation_engine.queue import QUEUE
from frappe.automation_engine.relationships import get_relationship_definitions
from frappe.automation_engine.runner import TASK_METHOD, execute_automation
from frappe.utils import now

TRIGGER_TYPES = [
	"Doc Created",
	"Doc Updated",
	"Field Value Changed",
	"Doc Deleted",
	"Doc Submitted",
	"Doc Cancelled",
	"Date Based",
	"Scheduled",
	"Custom Event",
	"Manual",
]


def _check_config_permission():
	frappe.has_permission("Automation Flow", "create", throw=True)


@frappe.whitelist()
def get_automation_capabilities(doctype: str | None = None, trigger_type: str | None = None) -> dict:
	"""Triggers, custom events, fields and serialized actions available for `doctype`."""
	_check_config_permission()
	if doctype:
		frappe.has_permission(doctype, throw=True)
	return {
		"triggers": TRIGGER_TYPES,
		"custom_events": registered_events(),
		"fields": _doc_fields(doctype) if doctype else [],
		"relationships": get_relationship_definitions(doctype),
		"actions": [
			a.as_dict() for a in get_action_registry().values() if _applies(a, doctype, trigger_type)
		],
	}


@frappe.whitelist()
def validate_action_params(
	action_type: str, doctype: str | None, params: str, trigger_type: str | None = None
) -> dict:
	"""Return {valid, errors:[{fieldname, message}]} for a single action's params."""
	_check_config_permission()
	action = get_action(action_type)
	try:
		_validate_action_context(action, doctype, trigger_type)
		action.validate(frappe.parse_json(params) or {}, doctype)
		return {"valid": True, "errors": []}
	except AutomationParamError as e:
		return {"valid": False, "errors": [{"fieldname": e.fieldname, "message": str(e)}]}
	except Exception as e:
		return {"valid": False, "errors": [{"fieldname": None, "message": str(e)}]}


@frappe.whitelist()
def get_param_options(
	action_type: str, fieldname: str, doctype: str, params: str | None = None, search_text: str | None = None
):
	"""Resolve dynamic options for a param via its schema-declared resolver only.

	Never dispatches to a client-supplied method path - only the fixed OPTION_RESOLVERS keyed
	by the param's declared `options_source` are callable.
	"""
	_check_config_permission()
	action = get_action(action_type)
	field = next((f for f in action.params_schema if f["fieldname"] == fieldname), None)
	if not field:
		frappe.throw(_("Unknown parameter: {0}").format(fieldname))
	parsed_params = frappe.parse_json(params) if params else {}
	_reject_client_methods(parsed_params)
	resolver = OPTION_RESOLVERS.get(field.get("options_source"))
	return resolver(doctype, parsed_params, search_text) if resolver else []


@frappe.whitelist()
def run_manually(automation: str, docname: str | None = None) -> dict:
	"""Queue a one-off run of `automation` against `docname` (Manual trigger / test button)."""
	rule = frappe.get_doc("Automation Flow", automation)
	frappe.has_permission("Automation Flow", "write", doc=rule, throw=True)
	if rule.document_type:
		frappe.has_permission(rule.document_type, "read", doc=docname, throw=True)
	elif docname:
		frappe.throw(_("Document-less automations do not accept a document name"))

	payload = {"manual": True, "manual_run_id": frappe.generate_hash(length=12)}
	queue_trigger(automation, rule.document_type, docname, payload=payload, depth=1)
	frappe.db.after_commit.add(kick_drainer)
	return {"queued": True}


@frappe.whitelist()
def get_runs(reference_doctype: str, reference_name: str) -> list:
	"""Return the run history for a document (timeline feed)."""
	frappe.has_permission(reference_doctype, "read", doc=reference_name, throw=True)
	tasks = frappe.get_all(
		"Background Task",
		filters={"ref_doctype": reference_doctype, "ref_docname": reference_name, "method": TASK_METHOD},
		fields=[
			"name",
			"arguments",
			"result",
			"status",
			"started_at",
			"ended_at",
			"exception",
		],
		order_by="creation desc",
	)
	return [_serialize_run(task) for task in tasks]


def _serialize_run(task) -> frappe._dict:
	arguments = frappe.parse_json(task.arguments) or {}
	result = frappe.parse_json(task.result) or {}
	return frappe._dict(
		name=task.name,
		automation=result.get("automation") or arguments.get("automation"),
		automation_title=result.get("automation_title") or arguments.get("automation_title"),
		status=result.get("automation_status") or task.status,
		started_at=task.started_at,
		ended_at=task.ended_at,
		error_summary=result.get("error_summary") or task.exception,
	)


def _doc_fields(doctype: str) -> list:
	# `options` travels with the field so a builder can offer the values a field actually
	# accepts - the target doctype for a Link, the choices for a Select - instead of a
	# free text box that only reveals its mistake at run time.
	return [
		{
			"fieldname": df.fieldname,
			"label": df.label,
			"fieldtype": df.fieldtype,
			"options": df.options,
		}
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype not in frappe.model.no_value_fields
	]


def _applies(action, doctype: str | None, trigger_type: str | None = None) -> bool:
	if action.requires_document and not doctype:
		return False
	if doctype and action.applicable_doctypes is not None and doctype not in action.applicable_doctypes:
		return False
	return (
		not trigger_type
		or not action.supported_trigger_types
		or trigger_type in action.supported_trigger_types
	)


def _validate_action_context(action, doctype, trigger_type):
	if action.requires_document and not doctype:
		raise AutomationParamError(_("This action requires a Document Type"))
	if trigger_type and action.supported_trigger_types and trigger_type not in action.supported_trigger_types:
		raise AutomationParamError(_("This action does not support the selected trigger"))


def _reject_client_methods(value):
	for item in _walk_values(value):
		if isinstance(item, str) and (item.startswith("method:") or item.startswith("frappe.")):
			frappe.throw(_("Client-supplied resolver methods are not allowed"))


def _walk_values(value):
	if isinstance(value, dict):
		for child in value.values():
			yield from _walk_values(child)
	elif isinstance(value, (list, tuple)):
		for child in value:
			yield from _walk_values(child)
	else:
		yield value


def _user_options(doctype, params, search_text):
	filters = {"enabled": 1}
	if search_text:
		filters["name"] = ("like", f"%{search_text}%")
	return frappe.get_all("User", filters=filters, fields=["name", "full_name"], limit=20)


# Fixed resolver table - the only server functions get_param_options may call.
OPTION_RESOLVERS = {
	"doc_fields": lambda doctype, params, search_text: _doc_fields(doctype),
	"users": _user_options,
}


TRIAL_SAVEPOINT = "automation_trial"


@frappe.whitelist()
def trial_run(automation: str, docname: str | None = None) -> dict:
	"""Execute `automation` against `docname` for real, then roll everything back.

	The runner builds its trace in memory, so the rollback discards every write the run made
	and still leaves the trace to return.
	"""
	rule = _trial_target(automation, docname)
	frappe.db.savepoint(TRIAL_SAVEPOINT)
	try:
		with _trial_mode():
			row_name = _trial_queue_row(rule, docname)
			execute_automation(row_name)
			return _trial_result(row_name, docname)
	finally:
		frappe.db.rollback(save_point=TRIAL_SAVEPOINT)


@contextmanager
def _trial_mode():
	"""Keep the trial inside the transaction, and out of the flow's live bookkeeping.

	An action that commits mid-step would make the trial real, and the circuit breaker (Redis)
	and realtime updates are not covered by a rollback either.
	"""
	original = frappe.db.commit
	previous = frappe.flags.get("in_automation_trial")
	frappe.db.commit = lambda *args, **kwargs: None
	frappe.flags.in_automation_trial = True
	try:
		yield
	finally:
		frappe.db.commit = original
		frappe.flags.in_automation_trial = previous


def _trial_target(automation: str, docname: str | None):
	rule = frappe.get_doc("Automation Flow", automation)
	frappe.has_permission("Automation Flow", "write", doc=rule, throw=True)
	if rule.document_type and docname:
		frappe.has_permission(rule.document_type, "read", doc=docname, throw=True)
	elif docname:
		frappe.throw(_("Document-less automations do not accept a document name"))
	return rule


def _trial_queue_row(rule, docname) -> str:
	# Inserted as Running, not Pending: dedup_key is NULL for a claimed row, so a trial never
	# collides with a genuine pending row for the same document.
	row = frappe.get_doc(
		{
			"doctype": QUEUE,
			"automation": rule.name,
			"ref_doctype": rule.document_type,
			"ref_name": docname,
			"status": "Running",
			"triggered_at": now(),
			"triggered_by": frappe.session.user,
			"depth": 1,
			"event_payload": frappe.as_json({"trial": True}),
		}
	).insert(ignore_permissions=True)
	return row.name


def _trial_result(row_name: str, docname: str | None) -> dict:
	result = frappe.db.get_value("Background Task", {"job_id": row_name}, "result")
	parsed = frappe.parse_json(result) if result else {}
	steps = parsed.get("steps") or []
	status = parsed.get("automation_status") or "Failed"
	return {
		"status": status,
		"document": docname,
		"steps": steps,
		"error_summary": parsed.get("error_summary"),
	}
