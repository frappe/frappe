# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

VALID_SCRIPT_CODE = "def main(city: str):\n\treturn f'sunny in {city}'\n"


def _module(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Tool",
		"title": "Get Weather",
		"slug": "get_weather",
		"type": "Imported",
		"description": "Returns weather for a city.",
		"import_path": "flow.tools.builtins.get_weather",
	}
	doc.update(overrides)
	return doc


def _script(**overrides: Any) -> dict:
	doc = _module(
		slug="script_weather",
		title="Script Weather",
		type="Script",
		import_path=None,
		code=VALID_SCRIPT_CODE,
	)
	doc.update(overrides)
	return doc


class IntegrationTestFlowTool(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_module_tool_creates_successfully(self):
		doc = frappe.get_doc(_module()).insert()
		self.assertEqual(doc.name, "get_weather")
		self.assertEqual(doc.type, "Imported")

	def test_script_tool_creates_successfully(self):
		doc = frappe.get_doc(_script()).insert()
		self.assertEqual(doc.name, "script_weather")
		self.assertEqual(doc.type, "Script")

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


class TestFlowToolSystemGenerated(IntegrationTestCase):
	"""Desk edits can't break system-generated tools; the owning app (ignore_permissions) can."""

	def tearDown(self):
		frappe.db.rollback()

	def _tool(self):
		return frappe.get_doc(_module(is_system_generated=1)).insert()

	def test_cannot_delete_via_desk(self):
		tool = self._tool()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"):
			frappe.delete_doc("Flow Tool", tool.name)

	def test_delete_blocked_even_with_ignore_permissions(self):
		tool = self._tool()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"):
			frappe.delete_doc("Flow Tool", tool.name, ignore_permissions=True)

	def test_cannot_unset_flag(self):
		tool = self._tool()
		tool.is_system_generated = 0
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot remove the system-generated flag"):
			tool.save()

	def test_cannot_change_import_path(self):
		tool = self._tool()
		tool.import_path = "flow.tools.builtins.execute"
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Import Path"):
			tool.save()

	def test_owning_app_can_change_import_path(self):
		tool = self._tool()
		tool.import_path = "flow.tools.builtins.execute"
		tool.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Flow Tool", tool.name, "import_path"), "flow.tools.builtins.execute"
		)

	def test_description_is_locked_but_enabled_stays_editable(self):
		tool = self._tool()
		tool.description = "Updated description."
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Description"):
			tool.save()
		tool.reload()
		tool.enabled = 0
		tool.save()
		self.assertEqual(frappe.db.get_value("Flow Tool", tool.name, "enabled"), 0)


class TestFlowToolSessionWarning(IntegrationTestCase):
	"""A tool change cannot reach the sessions the flow server already holds."""

	def setUp(self):
		model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Tool Warning Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.tool = frappe.get_doc(_module()).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Tool Warning Agent",
				"model": model.name,
				"instructions": "x",
				"tools": [{"tool": self.tool.name}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _session(self):
		frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert()

	def test_disabling_a_tool_warns_that_existing_sessions_keep_theirs(self):
		self._session()
		with patch("frappe.msgprint") as msgprint:
			self.tool.enabled = 0
			self.tool.save()

		self.assertIn("Existing sessions", msgprint.call_args.args[0])

	def test_an_edit_the_flow_server_never_sees_is_quiet(self):
		self._session()
		with patch("frappe.msgprint") as msgprint:
			self.tool.summary = "Weather, briefly."
			self.tool.save()

		msgprint.assert_not_called()

	def test_a_tool_no_session_uses_is_quiet(self):
		with patch("frappe.msgprint") as msgprint:
			self.tool.enabled = 0
			self.tool.save()

		msgprint.assert_not_called()
