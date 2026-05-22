# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

VALID_SCRIPT_CODE = "def main(city: str):\n\treturn f'sunny in {city}'\n"


def _module(**overrides: Any) -> dict:
	doc = {
		"doctype": "AI Tool",
		"title": "Get Weather",
		"slug": "get_weather",
		"kind": "Module",
		"description": "Returns weather for a city.",
		"import_path": "frappe.ai.tools.builtins.get_weather",
	}
	doc.update(overrides)
	return doc


def _script(**overrides: Any) -> dict:
	doc = _module(
		slug="script_weather",
		title="Script Weather",
		kind="Script",
		import_path=None,
		code=VALID_SCRIPT_CODE,
	)
	doc.update(overrides)
	return doc


class IntegrationTestAITool(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_module_tool_creates_successfully(self):
		doc = frappe.get_doc(_module()).insert()
		self.assertEqual(doc.name, "get_weather")
		self.assertEqual(doc.kind, "Module")

	def test_script_tool_creates_successfully(self):
		doc = frappe.get_doc(_script()).insert()
		self.assertEqual(doc.name, "script_weather")
		self.assertEqual(doc.kind, "Script")

	def test_slug_must_be_snake_case(self):
		for bad in ("bad-slug", "1starts_with_digit", "bad slug", "has.dot", "HasCaps"):
			with self.subTest(slug=bad), self.assertRaisesRegex(frappe.ValidationError, "Slug"):
				frappe.get_doc(_module(slug=bad)).insert()

	def test_slug_uniqueness_enforced(self):
		frappe.get_doc(_module()).insert()
		with self.assertRaises(frappe.exceptions.DuplicateEntryError):
			frappe.get_doc(_module()).insert()

	def test_module_requires_import_path(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Import Path"):
			frappe.get_doc(_module(import_path=None)).insert()

	def test_module_rejects_invalid_import_path(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Import Path"):
			frappe.get_doc(_module(import_path="not a path")).insert()

	def test_module_rejects_code(self):
		with self.assertRaisesRegex(frappe.ValidationError, "inline code"):
			frappe.get_doc(_module(code="def main():\n\treturn 1")).insert()

	def test_script_requires_code(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Code"):
			frappe.get_doc(_script(code=None)).insert()

	def test_script_rejects_import_path(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Import Path"):
			frappe.get_doc(_script(import_path="frappe.x.y")).insert()

	def test_script_rejects_syntax_error(self):
		with self.assertRaisesRegex(frappe.ValidationError, "syntax"):
			frappe.get_doc(_script(code="def main(:\n\tpass")).insert()

	def test_script_requires_main_function(self):
		with self.assertRaisesRegex(frappe.ValidationError, "main"):
			frappe.get_doc(_script(code="def other():\n\treturn 1\n")).insert()

	def test_script_rejects_varargs(self):
		with self.assertRaisesRegex(frappe.ValidationError, "args"):
			frappe.get_doc(_script(code="def main(*args, **kwargs):\n\treturn 1\n")).insert()

	def test_script_rejects_direct_main_call(self):
		code = "def main(city: str):\n\treturn city\n\nmain('x')\n"
		with self.assertRaisesRegex(frappe.ValidationError, "main"):
			frappe.get_doc(_script(code=code)).insert()
