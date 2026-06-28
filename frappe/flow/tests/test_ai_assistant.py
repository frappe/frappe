# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	sync_builtin_assistant,
)
from flow.tools.builtins import BUILTIN_TOOLS


class TestSyncBuiltinAssistant(IntegrationTestCase):
	def setUp(self):
		# Strip any Assistant from prior runs so each test starts clean.
		if frappe.db.exists("Flow Agent", ASSISTANT_AGENT_TITLE):
			frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "is_system_generated", 0)
			frappe.delete_doc("Flow Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Assistant Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_model_insert_auto_creates_assistant(self):
		# Model setUp insert triggers after_insert → sync_builtin_assistant.
		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)

		self.assertEqual(doc.model, self.model.name)
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)
		self.assertTrue(doc.is_system_generated)
		self.assertTrue(doc.enabled)
		expected_slugs = sorted(t.name for t in BUILTIN_TOOLS)
		self.assertEqual(sorted(row.tool for row in doc.tools), expected_slugs)

	def test_sync_updates_instructions_on_existing_system_agent(self):
		# sync_builtin_assistant should overwrite instructions on a system-generated agent.
		original = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		original.instructions = "stale instructions"
		original.save(ignore_permissions=True)

		sync_builtin_assistant(model=self.model.name)

		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)

	def test_sync_is_noop_for_user_owned_agent(self):
		# If is_system_generated was cleared (user took ownership), sync must not touch it.
		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "is_system_generated", 0)
		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "instructions", "user customised")

		sync_builtin_assistant(model=self.model.name)

		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertEqual(doc.instructions, "user customised")

	def test_assistant_cannot_be_deleted(self):
		with self.assertRaisesRegex(frappe.ValidationError, "system-generated"):
			frappe.delete_doc("Flow Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)
