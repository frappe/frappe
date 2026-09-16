# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from flow.tools.builtins import sync_builtin_tools


class TestFlowAgentToolChildTable(IntegrationTestCase):
	"""Flow Agent Tool is a Table MultiSelect child of Flow Agent with one required Link field.
	The interesting logic lives on the parent — these tests cover the row-level contract."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Test Agent Tool Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _agent(self, **overrides) -> dict:
		doc = {
			"doctype": "Flow Agent",
			"title": "Agent Tool Host",
			"model": self.model.name,
			"instructions": "x",
			"enabled": 1,
		}
		doc.update(overrides)
		return doc

	def test_child_rows_persist_through_parent(self):
		doc = frappe.get_doc(self._agent(tools=[{"tool": "read"}, {"tool": "execute"}])).insert()

		self.assertEqual([row.tool for row in doc.tools], ["read", "execute"])
		# Round-trip from DB to confirm the rows landed.
		reloaded = frappe.get_doc("Flow Agent", doc.name)
		self.assertEqual([row.tool for row in reloaded.tools], ["read", "execute"])

	def test_unknown_tool_link_rejected(self):
		doc = frappe.get_doc(self._agent(tools=[{"tool": "ghost_tool_does_not_exist"}]))

		with self.assertRaises(frappe.LinkValidationError):
			doc.insert()

	def test_empty_tool_field_rejected(self):
		doc = frappe.get_doc(self._agent(tools=[{"tool": None}]))

		with self.assertRaises(frappe.MandatoryError):
			doc.insert()
