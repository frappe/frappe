# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Convert a nested advanced-filter tree (AND/OR groups of arbitrary depth) into
the query engine's nested-list filter format.

The tree is the single data structure shared between the Desk advanced-filter UI
and the backend. It is purely additive: when no tree is supplied the existing flat
filter behaviour is byte-for-byte unchanged.

Node model (serialized as JSON)::

    Group: {"type": "group", "conjunction": "and" | "or", "children": [node, ...]}
    Rule:  {"type": "rule", "fieldname": str, "operator": str, "value": Any,
            "doctype": str | None}

The root node is always a Group. :func:`to_engine_filters` walks the tree exactly
once - optionally validating every rule leaf through a callback - and returns a
value accepted by :meth:`frappe.database.query.Engine.apply_filters` (which folds
``[cond, "and", cond, "or", cond]`` structures into composed pypika criteria via
:meth:`_parse_nested_filters`). Because every leaf flows back through the engine's
existing simple-filter builder, the operator semantics are identical to flat
filters - no new operator code is introduced.
"""

from collections.abc import Callable

import frappe
from frappe import _
from frappe.database.operator_map import NESTED_SET_OPERATORS, OPERATOR_MAP

#: Logical operators that join the children of a group.
CONJUNCTIONS = ("and", "or")

#: Present in ``OPERATOR_MAP`` for arithmetic expressions, but never valid as a
#: filter rule operator. Rejected explicitly so they cannot leak into a WHERE clause.
_ARITHMETIC_OPERATORS = frozenset({"+", "-", "*", "/"})

#: Operators the engine handles specially, outside of ``OPERATOR_MAP``.
_SPECIAL_OPERATORS = frozenset({"timespan", "previous", "next"})

#: Guard rails to bound recursion depth and the size of the generated SQL.
MAX_DEPTH = 20
MAX_RULES = 100


def is_valid_filter_operator(operator: str) -> bool:
	"""Return ``True`` if ``operator`` is a filter operator the query engine accepts.

	Mirrors the engine's own acceptance logic (``OPERATOR_MAP`` / nested-set /
	timespan / pluggable hook operators from ``additional_filters_config``) while
	explicitly rejecting arithmetic operators that would otherwise smuggle a
	non-boolean expression into the WHERE clause.
	"""
	if not isinstance(operator, str):
		return False

	operator = operator.strip()
	if not operator or operator in _ARITHMETIC_OPERATORS:
		return False

	lowered = operator.casefold()
	if lowered in _ARITHMETIC_OPERATORS:
		return False

	if lowered in _SPECIAL_OPERATORS or operator in NESTED_SET_OPERATORS or lowered in OPERATOR_MAP:
		return True

	# Pluggable operators contributed by apps via the `additional_filters_config` hook.
	from frappe.boot import get_additional_filters_from_hooks

	return lowered in get_additional_filters_from_hooks()


def to_engine_filters(
	tree: dict,
	validate_rule: Callable[[dict], None] | None = None,
) -> list | None:
	"""Convert a filter ``tree`` into the engine's nested-list filter format.

	The tree is walked a single time. For every rule leaf, ``validate_rule`` (when
	given) is invoked so the caller can apply the same field-existence and
	permission checks used for flat filters.

	Returns ``None`` when the tree carries no effective condition (e.g. an empty
	root group), in which case the caller should apply no filter at all.
	"""
	if not tree:
		return None

	counter = _RuleCounter()
	condition = _convert_node(tree, validate_rule, depth=0, counter=counter)
	if condition is None:
		return None

	# The desk/list path always passes filters as a *list of conditions*. A bare
	# simple-filter tuple (a single rule at the root) must therefore be wrapped, or
	# the query builder's argument heuristics mistake it for a list of fieldnames.
	if isinstance(condition[0], str):
		return [condition]

	return condition


class _RuleCounter:
	"""Tracks the number of rule leaves seen, to enforce :data:`MAX_RULES`."""

	__slots__ = ("count",)

	def __init__(self) -> None:
		self.count = 0


def _convert_node(
	node: dict,
	validate_rule: Callable[[dict], None] | None,
	depth: int,
	counter: _RuleCounter,
) -> list | None:
	if depth > MAX_DEPTH:
		frappe.throw(
			_("Filter is nested too deeply (maximum depth is {0}).").format(MAX_DEPTH),
			frappe.ValidationError,
		)

	if not isinstance(node, dict):
		frappe.throw(_("Invalid filter node: {0}").format(node), frappe.ValidationError)

	node_type = node.get("type")
	if node_type == "group":
		return _convert_group(node, validate_rule, depth, counter)

	if node_type == "rule":
		counter.count += 1
		if counter.count > MAX_RULES:
			frappe.throw(
				_("Too many filter rules (maximum is {0}).").format(MAX_RULES),
				frappe.ValidationError,
			)
		return _convert_rule(node, validate_rule)

	frappe.throw(_("Unknown filter node type: {0}").format(node_type), frappe.ValidationError)


def _convert_group(
	group: dict,
	validate_rule: Callable[[dict], None] | None,
	depth: int,
	counter: _RuleCounter,
) -> list | None:
	conjunction = (group.get("conjunction") or "and").casefold()
	if conjunction not in CONJUNCTIONS:
		frappe.throw(
			_("Invalid filter conjunction: {0}").format(group.get("conjunction")),
			frappe.ValidationError,
		)

	children = group.get("children") or []
	if not isinstance(children, list | tuple):
		frappe.throw(_("Filter group children must be a list."), frappe.ValidationError)

	# Empty sub-groups collapse to nothing and are simply dropped.
	parts = []
	for child in children:
		converted = _convert_node(child, validate_rule, depth + 1, counter)
		if converted is not None:
			parts.append(converted)

	if not parts:
		return None

	# A group with a single effective child contributes that child directly; the
	# conjunction is irrelevant with nothing to join.
	if len(parts) == 1:
		return parts[0]

	# Interleave children with the conjunction: [c0, conj, c1, conj, c2, ...].
	# A single conjunction folds associatively, so the engine's left-to-right
	# combination yields the correct result; nested groups remain explicitly
	# parenthesised because they are themselves lists.
	combined = [parts[0]]
	for part in parts[1:]:
		combined.append(conjunction)
		combined.append(part)
	return combined


def _convert_rule(rule: dict, validate_rule: Callable[[dict], None] | None) -> list:
	fieldname = rule.get("fieldname")
	operator = rule.get("operator")

	if not fieldname or not isinstance(fieldname, str):
		frappe.throw(_("Filter rule is missing a fieldname."), frappe.ValidationError)

	if not operator or not isinstance(operator, str):
		frappe.throw(_("Filter rule is missing an operator."), frappe.ValidationError)

	if not is_valid_filter_operator(operator):
		frappe.throw(_("Invalid filter operator: {0}").format(operator), frappe.ValidationError)

	# Field-existence and permission checks are delegated to the caller so they stay
	# identical to flat-filter validation (single source of truth, no drift).
	if validate_rule:
		validate_rule(rule)

	value = rule.get("value")
	doctype = rule.get("doctype")

	# A rule targeting another doctype (e.g. a child table) uses the 4-element form,
	# exactly like a flat ``[doctype, fieldname, operator, value]`` filter.
	if doctype:
		return [doctype, fieldname, operator, value]
	return [fieldname, operator, value]
