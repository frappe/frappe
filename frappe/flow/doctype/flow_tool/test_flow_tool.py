# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow.daemon import lifecycle
from frappe.flow.doctype.flow_tool.flow_tool import sync_server_tools
from frappe.flow.tools.builtins import sync_builtin_tools
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
		"import_path": "frappe.flow.tools.builtins.get_weather",
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


def _server(**overrides: Any) -> dict:
	doc = _module(slug="helpdesk_ticket", title="Helpdesk Ticket", type="Server", import_path=None)
	doc["is_system_generated"] = 1
	doc.update(overrides)
	return doc


class IntegrationTestFlowTool(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_an_invalid_tool_is_refused(self):
		cases = [
			(_module(slug=bad), "Slug")
			for bad in ("bad-slug", "1starts_with_digit", "bad slug", "has.dot", "HasCaps")
		]
		cases += [
			(_module(import_path=None), "Import Path"),
			(_module(import_path="not a path"), "Import Path"),
			(_module(code="def main():\n\treturn 1"), "inline code"),
			(_script(code=None), "Code"),
			(_script(import_path="frappe.x.y"), "Import Path"),
			(_script(code="def main(:\n\tpass"), "syntax"),
			(_script(code="def other():\n\treturn 1\n"), "main"),
			(_script(code="def main(*args, **kwargs):\n\treturn 1\n"), "args"),
			(_script(code="def main(city: str):\n\treturn city\n\nmain('x')\n"), "main"),
			(_server(code=VALID_SCRIPT_CODE), "no code here"),
			(_server(is_system_generated=0), "add an extension instead"),
		]
		for doc, error in cases:
			with self.subTest(doc=doc), self.assertRaisesRegex(frappe.ValidationError, error):
				frappe.get_doc(doc).insert()


class TestFlowToolSystemGenerated(IntegrationTestCase):
	"""Desk edits can't break system-generated tools; the owning app (ignore_permissions) can."""

	def tearDown(self):
		frappe.db.rollback()

	def test_the_desk_cannot_change_a_system_generated_tool_but_may_disable_it(self):
		sync_builtin_tools()
		tool = frappe.get_doc(_module(is_system_generated=1)).insert()
		for label, change in (
			("delete", lambda: frappe.delete_doc("Flow Tool", tool.name)),
			(
				"a builtin, even by the app",
				lambda: frappe.delete_doc("Flow Tool", "read", ignore_permissions=True),
			),
		):
			with (
				self.subTest(label),
				self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"),
			):
				change()
		for field, value, error in (
			("is_system_generated", 0, "Cannot remove the system-generated flag"),
			("import_path", "frappe.flow.tools.builtins.execute", "Cannot change Import Path"),
			("description", "Updated description.", "Cannot change Description"),
		):
			tool.reload()
			tool.set(field, value)
			with self.subTest(field=field), self.assertRaisesRegex(frappe.ValidationError, error):
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

	def test_only_a_change_the_flow_server_holds_warns_the_sessions_using_the_tool(self):
		with patch("frappe.msgprint") as msgprint:
			self.tool.enabled = 0
			self.tool.save()
		msgprint.assert_not_called()  # no session uses the tool yet

		frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert()
		with patch("frappe.msgprint") as msgprint:
			self.tool.summary = "Weather, briefly."
			self.tool.save()
		msgprint.assert_not_called()

		with patch("frappe.msgprint") as msgprint:
			self.tool.enabled = 1
			self.tool.save()
		self.assertIn("Existing sessions", msgprint.call_args.args[0])


def _listed(name: str, description: str, extension: str = "helpdesk") -> dict:
	return {"name": name, "description": description, "extension": extension}


class TestSyncServerTools(IntegrationTestCase):
	"""Server rows mirror the tools listed from this site's extensions folder."""

	def setUp(self):
		sync_builtin_tools()
		folder = TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.enterContext(patch.object(lifecycle, "site_extensions_dir", return_value=Path(folder.name)))

	def tearDown(self):
		frappe.db.rollback()

	def sync(self, *rows: dict) -> None:
		with patch.object(lifecycle, "extension_tools", return_value=list(rows)):
			sync_server_tools()

	def test_server_rows_follow_the_listing_and_take_their_agent_rows_along(self):
		self.sync(_listed("helpdesk_ticket", "Fetch a ticket."))
		tool = frappe.get_doc("Flow Tool", "helpdesk_ticket")
		self.assertEqual(
			(tool.type, tool.description, tool.is_system_generated), ("Server", "Fetch a ticket.", 1)
		)
		model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Sync Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()
		agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Sync Agent",
				"model": model.name,
				"instructions": "Be terse.",
				"tools": [{"tool": "helpdesk_ticket"}],
			}
		).insert()

		self.sync(_listed("helpdesk_ticket", "Fetch a ticket and its thread."))
		self.assertEqual(
			frappe.db.get_value("Flow Tool", "helpdesk_ticket", "description"),
			"Fetch a ticket and its thread.",
		)

		self.sync()
		self.assertFalse(frappe.db.exists("Flow Tool", "helpdesk_ticket"))
		self.assertEqual(frappe.get_all("Flow Agent Tool", {"parent": agent.name}), [])

	def test_an_extension_tool_that_cannot_have_a_server_row_is_skipped(self):
		with self.subTest("named like an app tool"), patch("frappe.log_error") as log_error:
			self.sync(_listed("read", "An override.", "override"))
			self.assertEqual(frappe.db.get_value("Flow Tool", "read", "type"), "Imported")
			log_error.assert_called_once()
		with self.subTest("a name that is not a slug"), patch("frappe.log_error") as log_error:
			self.sync(_listed("readTicket", "Fetch a ticket."))
			self.assertFalse(frappe.db.exists("Flow Tool", "readTicket"))
			log_error.assert_called_once()
