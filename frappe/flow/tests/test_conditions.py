# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.utils.conditions import evaluate_condition, validate_condition


class TestValidateCondition(IntegrationTestCase):
	def test_empty_condition_is_valid(self):
		validate_condition(None)
		validate_condition("")

	def test_expression_is_valid(self):
		validate_condition("doc.status == 'Open' and doc.priority == 'High'")

	def test_script_setting_result_is_valid(self):
		validate_condition("status = doc.status\nresult = status == 'Open'")

	def test_script_without_result_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "result"):
			validate_condition("status = doc.status")

	def test_syntax_error_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Invalid condition"):
			validate_condition("doc.status ==")

	def test_result_in_control_flow_is_valid(self):
		validate_condition("if doc.status == 'Open':\n\tresult = True\nelse:\n\tresult = False")

	def test_result_only_in_nested_scope_is_rejected(self):
		# `result` set inside a def never reaches the exec globals, so it must be rejected.
		with self.assertRaisesRegex(frappe.ValidationError, "result"):
			validate_condition("def check():\n\tresult = True")


class TestEvaluateCondition(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(cls.enable_safe_exec())

	def tearDown(self):
		frappe.db.rollback()

	def test_expression_verdict(self):
		doc = frappe._dict(status="Open")
		self.assertTrue(evaluate_condition("doc.status == 'Open'", {"doc": doc}))
		self.assertFalse(evaluate_condition("doc.status == 'Closed'", {"doc": doc}))

	def test_multiline_script_verdict(self):
		script = "words = doc.description.split()\nresult = len(words) > 2"
		self.assertTrue(evaluate_condition(script, {"doc": frappe._dict(description="a b c d")}))
		self.assertFalse(evaluate_condition(script, {"doc": frappe._dict(description="a b")}))

	def test_condition_can_query_db(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "db check", "status": "Closed"}).insert()
		condition = 'frappe.db.get_value("ToDo", doc.name, "status") == "Closed"'
		self.assertTrue(evaluate_condition(condition, {"doc": frappe._dict(name=todo.name)}))

	def test_runtime_error_raises(self):
		with self.assertRaises(Exception):
			evaluate_condition("undefined_name > 1", {"doc": frappe._dict()})

	def test_sandbox_blocks_imports(self):
		with self.assertRaises(Exception):
			evaluate_condition("import os\nresult = True", {"doc": frappe._dict()})
