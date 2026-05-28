# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.ai.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	ASSISTANT_TOOL_SLUGS,
	sync_builtin_assistant,
)
from frappe.tests import IntegrationTestCase


class TestSyncBuiltinAssistant(IntegrationTestCase):
	def setUp(self):
		# Strip any Assistant from prior runs so each test starts clean.
		if frappe.db.exists("AI Agent", ASSISTANT_AGENT_TITLE):
			frappe.db.set_value("AI Agent", ASSISTANT_AGENT_TITLE, "is_system_generated", 0)
			frappe.delete_doc("AI Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)
		self.model = frappe.get_doc(
			{
				"doctype": "AI Model",
				"title": "Assistant Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_model_insert_auto_creates_assistant(self):
		# Model setUp insert triggers after_insert → sync_builtin_assistant.
		doc = frappe.get_doc("AI Agent", ASSISTANT_AGENT_TITLE)

		self.assertEqual(doc.model, self.model.name)
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)
		self.assertTrue(doc.is_system_generated)
		self.assertTrue(doc.enabled)
		self.assertEqual(sorted(row.tool for row in doc.tools), sorted(ASSISTANT_TOOL_SLUGS))

	def test_sync_is_noop_when_assistant_exists(self):
		original = frappe.get_doc("AI Agent", ASSISTANT_AGENT_TITLE)
		original.instructions = "custom tweak"
		original.save(ignore_permissions=True)

		sync_builtin_assistant(model=self.model.name)

		doc = frappe.get_doc("AI Agent", ASSISTANT_AGENT_TITLE)
		self.assertEqual(doc.instructions, "custom tweak")

	def test_assistant_cannot_be_deleted(self):
		with self.assertRaisesRegex(frappe.ValidationError, "system-generated"):
			frappe.delete_doc("AI Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)
