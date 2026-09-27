# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	sync_builtin_assistant,
)
from flow.assistant.assistant import ASSISTANT_MAX_ITERATIONS
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

	def test_install_adds_builtin_tools_before_any_model(self):
		self.assertIn(
			"flow.assistant.sync_builtin_assistant", frappe.get_hooks("after_install", app_name="flow")
		)
		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "is_system_generated", 0)
		frappe.delete_doc("Flow Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		builtins = [t.name for t in BUILTIN_TOOLS]
		frappe.db.delete("Flow Tool", {"name": ("in", builtins)})

		sync_builtin_assistant()

		self.assertEqual(
			sorted(frappe.get_all("Flow Tool", {"name": ("in", builtins)}, pluck="name")), sorted(builtins)
		)
		self.assertFalse(frappe.db.exists("Flow Agent", ASSISTANT_AGENT_TITLE))

	def test_sync_updates_instructions_on_existing_system_agent(self):
		# sync_builtin_assistant should overwrite instructions on a system-generated agent.
		original = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		original.instructions = "stale instructions"
		original.save(ignore_permissions=True)

		sync_builtin_assistant(model=self.model.name)

		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)

	def test_sync_restores_the_complete_definition_but_keeps_site_choices(self):
		other_model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Other Assistant Model",
				"model_id": "openai/gpt-4o",
				"enabled": 1,
			}
		).insert()
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		knowledge = frappe.get_doc(
			{"doctype": "Flow Knowledge Base", "title": "Stale Assistant Knowledge"}
		).insert()
		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		doc.update(
			{
				"instructions": "stale instructions",
				"max_iterations": 3,
				"model": other_model.name,
				"enabled": 0,
			}
		)
		doc.set("tools", [{"tool": BUILTIN_TOOLS[0].name}])
		doc.set("knowledge_bases", [{"knowledge_base": knowledge.name}])
		doc.save(ignore_permissions=True)

		sync_builtin_assistant(model=self.model.name)

		doc.reload()
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)
		self.assertEqual(doc.max_iterations, ASSISTANT_MAX_ITERATIONS)
		self.assertEqual([row.tool for row in doc.tools], [tool.name for tool in BUILTIN_TOOLS])
		self.assertEqual([row.knowledge_base for row in doc.knowledge_bases], [])
		self.assertEqual((doc.model, doc.enabled), (other_model.name, 0))

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

	def test_a_later_model_leaves_the_assistant_alone(self):
		with patch("flow.assistant.assistant.sync_builtin_assistant") as sync:
			self.insert_model("Second Model")
		sync.assert_not_called()

	def test_a_new_model_replaces_one_the_assistant_lost(self):
		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "model", "Gone Model")

		second = self.insert_model("Second Model")

		self.assertEqual(frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_TITLE, "model"), second.name)

	def insert_model(self, title: str):
		return frappe.get_doc(
			{"doctype": "Flow Model", "title": title, "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
