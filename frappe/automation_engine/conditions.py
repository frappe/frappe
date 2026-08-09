# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Structured conditions over registered, related records.

A related condition never loads the related documents: it compiles the filters through the
provider's query and only counts what comes back, so an existence check on a large table stays
a bounded query.
"""

import frappe
from frappe import _
from frappe.automation_engine.relationships import (
	get_relationship_definition,
	load_record,
	query_related,
)

EXISTENCE_OPERATORS = ("RelatedExists", "RelatedNotExists")
OPERATORS = (*EXISTENCE_OPERATORS, "RelatedCount")
COMPARISONS = {
	"=": lambda count, value: count == value,
	"!=": lambda count, value: count != value,
	">": lambda count, value: count > value,
	">=": lambda count, value: count >= value,
	"<": lambda count, value: count < value,
	"<=": lambda count, value: count <= value,
}


def validate_related_condition(stored, targets):
	"""Check a saved condition against the flow's aliases and registered relationships."""
	condition = _parse(stored)
	if not condition:
		return
	source = condition["source"]
	if source not in targets:
		frappe.throw(_("Unknown related-condition source alias: {0}").format(source))
	if targets[source]:
		get_relationship_definition(targets[source], condition["relationship"])


def evaluate_related_condition(stored, context) -> bool:
	condition = _parse(stored)
	if not condition:
		return True
	source = load_record(context["records"].get(condition["source"]), permission_type="read")
	filters = _render_filters(condition["filters"], context)
	limit = 1 if condition["type"] in EXISTENCE_OPERATORS else None
	count = len(query_related(source, condition["relationship"], filters, limit))
	return _compare(condition, count)


def _parse(stored) -> dict | None:
	if not stored:
		return None
	condition = frappe.parse_json(stored) if isinstance(stored, str) else stored
	if not isinstance(condition, dict):
		frappe.throw(_("Related record condition must be a JSON object"))
	operator = condition.get("type") or "RelatedExists"
	if operator not in OPERATORS:
		frappe.throw(_("Unsupported related condition: {0}").format(operator))
	if not condition.get("relationship"):
		frappe.throw(_("Related record condition needs a relationship"))
	return {
		"type": operator,
		"source": condition.get("source") or "trigger",
		"relationship": condition["relationship"],
		"filters": condition.get("filters") or [],
		"comparison": condition.get("comparison") or ">=",
		"value": frappe.utils.cint(condition.get("value", 1)),
	}


def _compare(condition, count) -> bool:
	if condition["type"] == "RelatedExists":
		return count > 0
	if condition["type"] == "RelatedNotExists":
		return count == 0
	comparison = COMPARISONS.get(condition["comparison"])
	if not comparison:
		frappe.throw(_("Unsupported count comparison: {0}").format(condition["comparison"]))
	return comparison(count, condition["value"])


def _render_filters(filters, context):
	"""Render Jinja in the filter values.

	Only the aliases a template actually names are loaded — a flow with a dozen aliases and a
	filter that mentions one must not fetch (and permission-check) the other eleven.
	"""
	templates = list(_templates(filters))
	if not templates:
		return filters
	return _render_value(filters, _template_context(context, templates))


def _templates(value):
	if isinstance(value, str):
		if "{{" in value:
			yield value
	elif isinstance(value, list):
		for item in value:
			yield from _templates(item)
	elif isinstance(value, dict):
		yield from _templates(list(value.values()))


def _template_context(context, templates) -> dict:
	referenced = {
		alias: reference
		for alias, reference in context["records"].items()
		if any(alias in template for template in templates)
	}
	records = {
		alias: load_record(reference, permission_type="read")
		for alias, reference in referenced.items()
	}
	return {"context": context, **records}


def _render_value(value, render_context):
	if isinstance(value, str) and "{{" in value:
		return frappe.render_template(value, render_context)
	if isinstance(value, list):
		return [_render_value(item, render_context) for item in value]
	if isinstance(value, dict):
		return {key: _render_value(item, render_context) for key, item in value.items()}
	return value
