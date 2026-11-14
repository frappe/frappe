# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.flow.utils.conditions import evaluate_condition, validate_condition
from frappe.tests import IntegrationTestCase


class TestConditions(IntegrationTestCase):
	def test_validate_condition_needs_a_single_expression(self):
		for condition in (None, "", "doc.status == 'Open' and doc.priority == 'High'"):
			with self.subTest(condition=condition):
				validate_condition(condition)

		for condition in ("doc.status ==", "status = doc.status\nresult = status == 'Open'"):
			with (
				self.subTest(condition=condition),
				self.assertRaisesRegex(frappe.ValidationError, "single Python expression"),
			):
				validate_condition(condition)

	def test_evaluate_condition_sees_only_what_it_is_given(self):
		for condition, doc, verdict in (
			("doc.status == 'Open'", frappe._dict(status="Open"), True),
			("doc.status == 'Closed'", frappe._dict(status="Open"), False),
			("len(doc['items']) > 1", frappe._dict(items=[1, 2]), True),
		):
			with self.subTest(condition=condition, doc=doc):
				self.assertIs(evaluate_condition(condition, {"doc": doc}), verdict)

		for condition in (
			"frappe.db.get_value('User', 'Administrator', 'name')",
			"open('/etc/passwd')",
			"doc.__class__",
			"(lambda: 1)()",
			"status = 'Open'",
		):
			with self.subTest(condition=condition), self.assertRaises(Exception):
				evaluate_condition(condition, {"doc": frappe._dict()})
