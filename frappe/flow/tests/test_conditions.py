# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow.utils.conditions import evaluate_condition, validate_condition
from frappe.tests import IntegrationTestCase


class TestConditions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))

	def tearDown(self):
		frappe.db.rollback()

	def test_validate_condition_needs_an_expression_or_a_script_setting_result(self):
		for condition, error in (
			(None, None),
			("", None),
			("doc.status == 'Open' and doc.priority == 'High'", None),
			("status = doc.status\nresult = status == 'Open'", None),
			("if doc.status == 'Open':\n\tresult = True\nelse:\n\tresult = False", None),
			("status = doc.status", "result"),
			("doc.status ==", "Invalid condition"),
			# `result` set inside a def never reaches the exec globals
			("def check():\n\tresult = True", "result"),
		):
			with self.subTest(condition=condition):
				if error:
					with self.assertRaisesRegex(frappe.ValidationError, error):
						validate_condition(condition)
				else:
					validate_condition(condition)

	def test_evaluate_condition_returns_the_verdict_from_the_sandbox(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "db check", "status": "Closed"}).insert()
		script = "words = doc.description.split()\nresult = len(words) > 2"
		for condition, doc, verdict in (
			("doc.status == 'Open'", frappe._dict(status="Open"), True),
			("doc.status == 'Closed'", frappe._dict(status="Open"), False),
			(script, frappe._dict(description="a b c d"), True),
			(script, frappe._dict(description="a b"), False),
			(
				'frappe.db.get_value("ToDo", doc.name, "status") == "Closed"',
				frappe._dict(name=todo.name),
				True,
			),
		):
			with self.subTest(condition=condition, doc=doc):
				self.assertIs(evaluate_condition(condition, {"doc": doc}), verdict)

		# a runtime error, or an import the sandbox blocks
		for condition in ("undefined_name > 1", "import os\nresult = True"):
			with self.subTest(condition=condition), self.assertRaises(Exception):
				evaluate_condition(condition, {"doc": frappe._dict()})
