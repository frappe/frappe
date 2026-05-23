# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any

import frappe
from frappe.ai.tester import run_in_rollback, test_tool
from frappe.ai.tool import tool
from frappe.tests import IntegrationTestCase


@tool
def _insert_todo() -> str:
	"""Insert a ToDo and return its name."""
	doc = frappe.get_doc({"doctype": "ToDo", "description": "rollback probe"}).insert()
	return doc.name


@tool
def _boom() -> str:
	"""Always raises."""
	raise RuntimeError("kaboom")


@tool
def _add(a: int, b: int) -> int:
	"""Add two numbers."""
	return a + b


SCRIPT_INSERT = (
	"def main():\n"
	"\tdoc = frappe.get_doc({'doctype': 'ToDo', 'description': 'script probe'}).insert()\n"
	"\treturn doc.name\n"
)
SCRIPT_COMMIT = (
	"def main():\n"
	"\tfrappe.get_doc({'doctype': 'ToDo', 'description': 'sneaky'}).insert()\n"
	"\tfrappe.db.commit()\n"
	"\treturn 'committed'\n"
)
SCRIPT_RAISES = "def main():\n\traise ValueError('bad input')\n"


def _script_doc(slug: str, code: str) -> dict[str, Any]:
	return {
		"doctype": "AI Tool",
		"title": slug,
		"slug": slug,
		"kind": "Script",
		"description": "Test script tool.",
		"code": code,
	}


class TestRunInRollback(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_successful_write_is_rolled_back(self):
		before = frappe.db.count("ToDo")
		outcome = run_in_rollback(_insert_todo, {})

		self.assertTrue(outcome.ok)
		self.assertIsInstance(outcome.result, str)
		self.assertEqual(frappe.db.count("ToDo"), before)

	def test_error_is_captured(self):
		outcome = run_in_rollback(_boom, {})

		self.assertFalse(outcome.ok)
		self.assertIn("kaboom", outcome.error)
		self.assertIn("RuntimeError", outcome.error)

	def test_result_is_returned(self):
		outcome = run_in_rollback(_add, {"a": 2, "b": 3})

		self.assertTrue(outcome.ok)
		self.assertEqual(outcome.result, 5)


class TestToolTester(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_script_write_is_rolled_back(self):
		doc = frappe.get_doc(_script_doc("probe_insert", SCRIPT_INSERT)).insert()
		before = frappe.db.count("ToDo")

		outcome = test_tool(doc)

		self.assertTrue(outcome.ok)
		self.assertIsInstance(outcome.result, str)
		self.assertEqual(frappe.db.count("ToDo"), before)

	def test_script_commit_is_blocked_and_rolled_back(self):
		doc = frappe.get_doc(_script_doc("probe_commit", SCRIPT_COMMIT)).insert()
		before = frappe.db.count("ToDo")

		outcome = test_tool(doc)

		self.assertFalse(outcome.ok)
		self.assertEqual(frappe.db.count("ToDo"), before)

	def test_script_error_is_captured(self):
		doc = frappe.get_doc(_script_doc("probe_raises", SCRIPT_RAISES)).insert()

		outcome = test_tool(doc)

		self.assertFalse(outcome.ok)
		self.assertIn("bad input", outcome.error)
