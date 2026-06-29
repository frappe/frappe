# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.reportview import execute, get_form_params
from frappe.model.filter_tree import (
	MAX_DEPTH,
	MAX_RULES,
	is_valid_filter_operator,
	to_engine_filters,
)
from frappe.tests import IntegrationTestCase


def rule(fieldname, operator, value, doctype=None):
	node = {"type": "rule", "fieldname": fieldname, "operator": operator, "value": value}
	if doctype:
		node["doctype"] = doctype
	return node


def group(conjunction, *children):
	return {"type": "group", "conjunction": conjunction, "children": list(children)}


class TestFilterTreeConversion(IntegrationTestCase):
	"""Pure-conversion tests: tree -> engine nested-list format."""

	def test_empty_tree_returns_none(self):
		self.assertIsNone(to_engine_filters(None))
		self.assertIsNone(to_engine_filters({}))
		self.assertIsNone(to_engine_filters(group("and")))

	def test_single_rule_is_wrapped_as_list_of_conditions(self):
		# A bare 3-tuple at the root would be mistaken for a list of fieldnames by the
		# query builder, so a single rule must come back wrapped in an outer list.
		self.assertEqual(
			to_engine_filters(group("and", rule("status", "=", "Open"))),
			[["status", "=", "Open"]],
		)

	def test_flat_and_group(self):
		self.assertEqual(
			to_engine_filters(group("and", rule("a", "=", 1), rule("b", "=", 2))),
			[["a", "=", 1], "and", ["b", "=", 2]],
		)

	def test_flat_or_group(self):
		self.assertEqual(
			to_engine_filters(group("or", rule("a", "=", 1), rule("b", "=", 2))),
			[["a", "=", 1], "or", ["b", "=", 2]],
		)

	def test_nested_group_is_parenthesised(self):
		tree = group(
			"or",
			group("and", rule("a", "=", 1), rule("b", "=", 2)),
			rule("c", "=", 3),
		)
		self.assertEqual(
			to_engine_filters(tree),
			[[["a", "=", 1], "and", ["b", "=", 2]], "or", ["c", "=", 3]],
		)

	def test_single_child_group_is_unwrapped(self):
		# A group with one effective child contributes that child directly; an empty
		# sibling sub-group simply disappears.
		tree = group("and", rule("a", "=", 1), group("or"))
		self.assertEqual(to_engine_filters(tree), [["a", "=", 1]])

	def test_rule_with_explicit_doctype_uses_four_element_form(self):
		tree = group("and", rule("qty", ">", 5, doctype="Sales Order Item"))
		self.assertEqual(to_engine_filters(tree), [["Sales Order Item", "qty", ">", 5]])

	def test_list_value_is_preserved_for_in_operator(self):
		tree = group("and", rule("status", "in", ["Open", "Closed"]))
		self.assertEqual(to_engine_filters(tree), [["status", "in", ["Open", "Closed"]]])

	def test_conjunction_defaults_to_and_and_is_case_insensitive(self):
		tree = {
			"type": "group",
			"conjunction": "OR",
			"children": [rule("a", "=", 1), rule("b", "=", 2)],
		}
		self.assertEqual(to_engine_filters(tree), [["a", "=", 1], "or", ["b", "=", 2]])


class TestFilterTreeValidation(IntegrationTestCase):
	"""Structural and operator validation of the tree, independent of any doctype."""

	def test_invalid_operator_raises(self):
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(group("and", rule("a", "definitely not an operator", 1)))

	def test_arithmetic_operators_are_rejected(self):
		for op in ("+", "-", "*", "/"):
			with self.assertRaises(frappe.ValidationError):
				to_engine_filters(group("and", rule("a", op, 1)))

	def test_missing_fieldname_raises(self):
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(group("and", {"type": "rule", "operator": "=", "value": 1}))

	def test_missing_operator_raises(self):
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(group("and", {"type": "rule", "fieldname": "a", "value": 1}))

	def test_unknown_node_type_raises(self):
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters({"type": "banana", "children": []})

	def test_invalid_conjunction_raises(self):
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(
				{"type": "group", "conjunction": "xor", "children": [rule("a", "=", 1)]}
			)

	def test_max_depth_is_enforced(self):
		node = rule("a", "=", 1)
		for _ in range(MAX_DEPTH + 5):
			node = group("and", node)
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(node)

	def test_max_rules_is_enforced(self):
		rules = [rule(f"field_{i}", "=", i) for i in range(MAX_RULES + 1)]
		with self.assertRaises(frappe.ValidationError):
			to_engine_filters(group("or", *rules))

	def test_validate_rule_callback_is_invoked_for_every_leaf(self):
		seen = []
		tree = group(
			"or",
			group("and", rule("a", "=", 1), rule("b", "=", 2)),
			rule("c", "=", 3),
		)
		to_engine_filters(tree, validate_rule=lambda r: seen.append(r["fieldname"]))
		self.assertEqual(sorted(seen), ["a", "b", "c"])


class TestIsValidFilterOperator(IntegrationTestCase):
	def test_accepts_standard_filter_operators(self):
		for op in ("=", "!=", "<", ">", ">=", "<=", "like", "not like", "in", "not in", "is", "between"):
			self.assertTrue(is_valid_filter_operator(op), op)

	def test_accepts_special_and_nested_set_operators(self):
		self.assertTrue(is_valid_filter_operator("timespan"))
		self.assertTrue(is_valid_filter_operator("ancestors of"))
		self.assertTrue(is_valid_filter_operator("descendants of"))

	def test_rejects_logical_arithmetic_and_garbage(self):
		for op in ("and", "or", "+", "-", "*", "/", "", "   ", "drop", None, 123):
			self.assertFalse(is_valid_filter_operator(op), op)


class TestFilterTreeQueryResults(IntegrationTestCase):
	"""End-to-end correctness: the generated SQL must return the right rows.

	Comparisons are made against the *same* query engine (``frappe.qb.get_query``)
	using equivalent flat / or filters, so the tree path is verified apples-to-apples.
	"""

	def _names(self, **kwargs):
		query = frappe.qb.get_query("DocType", fields=["name"], **kwargs)
		return {row["name"] for row in query.run(as_dict=True)}

	def test_and_group_matches_flat_filters(self):
		tree = group("and", rule("issingle", "=", 1), rule("module", "=", "Core"))
		self.assertEqual(
			self._names(filters=to_engine_filters(tree)),
			self._names(filters=[["issingle", "=", 1], ["module", "=", "Core"]]),
		)

	def test_or_group_matches_or_filters(self):
		tree = group("or", rule("issingle", "=", 1), rule("istable", "=", 1))
		got = self._names(filters=to_engine_filters(tree))
		reference = self._names(or_filters=[["issingle", "=", 1], ["istable", "=", 1]])
		self.assertEqual(got, reference)
		self.assertTrue(got, "expected at least one single or child-table doctype")

	def test_nested_group_matches_python_reference(self):
		# (module = Core AND issingle = 1) OR (module = Core AND istable = 1)
		tree = group(
			"or",
			group("and", rule("module", "=", "Core"), rule("issingle", "=", 1)),
			group("and", rule("module", "=", "Core"), rule("istable", "=", 1)),
		)
		got = self._names(filters=to_engine_filters(tree))

		all_doctypes = frappe.get_all(
			"DocType", fields=["name", "module", "issingle", "istable"]
		)
		expected = {
			d.name for d in all_doctypes if d.module == "Core" and (d.issingle or d.istable)
		}
		self.assertEqual(got, expected)


class TestFilterTreeReportView(IntegrationTestCase):
	"""Full request path: parse -> validate -> convert -> execute."""

	def _run(self, doctype, tree, fields=None):
		original = getattr(frappe.local, "form_dict", None)
		try:
			frappe.local.form_dict = frappe._dict(
				doctype=doctype,
				filter_tree=json.dumps(tree),
				fields=json.dumps(fields or ["name"]),
				save_user_settings="false",
			)
			args = get_form_params()
			# The tree must be fully consumed and never forwarded to the executor.
			self.assertNotIn("filter_tree", args)
			return execute(**args)
		finally:
			frappe.local.form_dict = original if original is not None else frappe._dict()

	def test_full_path_applies_advanced_filters(self):
		tree = group("and", rule("issingle", "=", 1), rule("module", "=", "Core"))
		names = {row["name"] for row in self._run("DocType", tree)}
		reference = {d.name for d in frappe.get_all("DocType", filters={"issingle": 1, "module": "Core"})}
		self.assertEqual(names, reference)

	def test_nonexistent_field_is_rejected(self):
		tree = group("and", rule("totally_made_up_field_xyz", "=", "x"))
		with self.assertRaises(frappe.DataError):
			self._run("DocType", tree)

	def test_invalid_operator_is_rejected(self):
		tree = group("and", rule("module", "totally_invalid_op", "x"))
		with self.assertRaises(frappe.ValidationError):
			self._run("DocType", tree)

	def test_fieldname_injection_is_rejected(self):
		tree = group("and", rule("name) OR 1=1 -- ", "=", "x"))
		with self.assertRaises((frappe.DataError, frappe.ValidationError)):
			self._run("DocType", tree)
