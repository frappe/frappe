# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import ast

import frappe
from frappe import _
from frappe.automation_engine.relationships import (
	get_relationship_definition,
	load_record,
	query_related,
)
from frappe.utils import cint

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


CONJUNCTIONS = ("and", "or")
# The condition builder writes Python-style equality; frappe's filter grammar wants "=".
OPERATOR_ALIASES = {"==": "="}


def evaluate_filter_tree(doc, filters) -> bool:
	"""Evaluate the builder's condition list, which `evaluate_filters` cannot.

	The list view builder stores leaf rows `[field, operator, value]` with "and"/"or" between
	them, and a nested list wherever rows were grouped. `frappe.utils.evaluate_filters` only
	ANDs a flat list, so an "or" saved from the builder would be silently ignored.

	An empty list matches, so a flow with no filters runs.
	"""
	from frappe.utils import evaluate_filters

	if not filters:
		return True
	if not _has_conjunctions(filters):
		return evaluate_filters(doc, [_normalise_row(row) for row in filters])
	return _evaluate_sequence(doc, filters)


def _normalise_row(row):
	"""Rewrite an operator the builder spells differently to the one frappe accepts."""
	if isinstance(row, list | tuple) and len(row) >= 2 and row[1] in OPERATOR_ALIASES:
		return [row[0], OPERATOR_ALIASES[row[1]], *list(row)[2:]]
	return row


def _has_conjunctions(filters) -> bool:
	"""A plain list of rows means "all of these", and is left to `evaluate_filters`."""
	return any(isinstance(item, str) and item in CONJUNCTIONS for item in filters)


def _evaluate_sequence(doc, filters) -> bool:
	"""`or` binds looser than `and`, so split on `or` and require one group to pass."""
	groups, current = [], []
	for item in filters:
		if isinstance(item, str) and item == "or":
			groups.append(current)
			current = []
		elif isinstance(item, str) and item == "and":
			continue
		else:
			current.append(item)
	groups.append(current)
	return any(all(_evaluate_operand(doc, operand) for operand in group) for group in groups)


def _evaluate_operand(doc, operand) -> bool:
	"""A group is a list whose first entry is itself a list; anything else is a leaf row."""
	if isinstance(operand, list | tuple) and operand and isinstance(operand[0], list | tuple):
		return evaluate_filter_tree(doc, list(operand))
	return evaluate_filter_tree(doc, [operand])


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
		"value": cint(condition.get("value", 1)),
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

	Only the aliases a template actually names are loaded - a flow with a dozen aliases and a
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
		alias: load_record(reference, permission_type="read") for alias, reference in referenced.items()
	}
	return {"context": context, **records}


def _render_value(value, render_context):
	if isinstance(value, str) and "{{" in value:
		# nosemgrep: the template is a saved related-condition filter value, authored with the flow.
		return frappe.render_template(value, render_context)
	if isinstance(value, list):
		return [_render_value(item, render_context) for item in value]
	if isinstance(value, dict):
		return {key: _render_value(item, render_context) for key, item in value.items()}
	return value


def condition_fieldnames(condition: str) -> set[str] | None:
	"""Fieldnames a condition reads off `doc`, or None when a field row cannot answer it.

	None is the "load the real document" signal: the expression does not parse, or it reaches
	through something other than a bare `doc.<field>` - a method call, a chained attribute,
	another record. Only the flat case is safe to serve from a bulk column fetch.
	"""
	try:
		tree = ast.parse(condition or "", mode="eval")
	except (SyntaxError, ValueError):
		return None

	names = set()
	for node in ast.walk(tree):
		if not isinstance(node, ast.Attribute):
			continue
		if not isinstance(node.value, ast.Name) or node.value.id != "doc":
			return None
		names.add(node.attr)
	return names


def condition_values(condition: str, scope: dict) -> dict:
	"""Values of every `doc.x` / `target.x` a condition reads, keyed by the source text.

	Sitting the values a condition actually saw next to its source is what turns "step
	skipped" into a diagnosis. Reading them off the parse tree keeps it generic: no app
	knows, no operator table, and anything unparseable simply reports nothing.
	"""
	try:
		tree = ast.parse(condition or "", mode="eval")
	except (SyntaxError, ValueError):
		return {}

	values = {}
	for node in ast.walk(tree):
		if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
			continue
		record = scope.get(node.value.id)
		if record is None:
			continue
		values[f"{node.value.id}.{node.attr}"] = record.get(node.attr)
	return values
