# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Whitelisted, permission-checked endpoints that drive the shared builder UI."""

import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationParamError, get_action, get_action_registry

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
def get_automation_capabilities(doctype: str) -> dict:
	"""Triggers, custom events, fields and serialized actions available for `doctype`."""
	_check_config_permission()
	frappe.has_permission(doctype, throw=True)
	return {
		"triggers": TRIGGER_TYPES,
		"custom_events": frappe.get_hooks("automation_events"),
		"fields": _doc_fields(doctype),
		"actions": [a.as_dict() for a in get_action_registry().values() if _applies(a, doctype)],
	}


@frappe.whitelist()
def validate_action_params(action_type: str, doctype: str, params: str) -> dict:
	"""Return {valid, errors:[{fieldname, message}]} for a single action's params."""
	_check_config_permission()
	action = get_action(action_type)
	try:
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

	Never dispatches to a client-supplied method path — only the fixed OPTION_RESOLVERS keyed
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
def run_manually(automation: str, docname: str) -> dict:
	"""Queue a one-off run of `automation` against `docname` (Manual trigger / test button)."""
	from frappe.automation_engine.dispatch import kick_drainer, queue_trigger

	rule = frappe.get_doc("Automation Flow", automation)
	frappe.has_permission("Automation Flow", "write", doc=rule, throw=True)
	frappe.has_permission(rule.document_type, "read", doc=docname, throw=True)

	queue_trigger(automation, rule.document_type, docname, payload={"manual": True}, depth=1)
	frappe.db.after_commit.add(kick_drainer)
	return {"queued": True}


@frappe.whitelist()
def get_runs(reference_doctype: str, reference_name: str) -> list:
	"""Return the run history for a document (timeline feed)."""
	frappe.has_permission(reference_doctype, "read", doc=reference_name, throw=True)
	return frappe.get_all(
		"Automation Run",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=["name", "automation", "automation_title", "status", "started_at", "ended_at", "error_summary"],
		order_by="creation desc",
	)


def _doc_fields(doctype: str) -> list:
	return [
		{"fieldname": df.fieldname, "label": df.label, "fieldtype": df.fieldtype}
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype not in frappe.model.no_value_fields
	]


def _applies(action, doctype: str) -> bool:
	return action.applicable_doctypes is None or doctype in action.applicable_doctypes


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


# Fixed resolver table — the only server functions get_param_options may call.
OPTION_RESOLVERS = {
	"doc_fields": lambda doctype, params, search_text: _doc_fields(doctype),
	"users": _user_options,
}
