# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import shutil
from unittest.mock import patch

import frappe
from frappe.flow.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	sync_assistant_skills,
	sync_builtin_assistant,
)
from frappe.flow.assistant.assistant import ASSISTANT_MAX_ITERATIONS
from frappe.flow.doctype.flow_agent.flow_agent import MAX_SKILLS
from frappe.flow.doctype.flow_skill.test_flow_skill import AppSkills
from frappe.flow.tools.builtins import BUILTIN_TOOLS
from frappe.tests import IntegrationTestCase
from frappe.utils import get_weekday, today


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

	def test_model_insert_auto_creates_a_locked_assistant(self):
		# Model setUp insert triggers after_insert → sync_builtin_assistant.
		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)

		self.assertEqual(doc.model, self.model.name)
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)
		self.assertTrue(doc.is_system_generated)
		self.assertTrue(doc.enabled)
		expected_slugs = sorted(t.name for t in BUILTIN_TOOLS)
		self.assertEqual(sorted(row.tool for row in doc.tools), expected_slugs)
		self.assertIn(
			f"You are helping Administrator (Administrator). Session started on {get_weekday()}, {today()}.",
			doc.render_instructions(),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "system-generated"):
			frappe.delete_doc("Flow Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True)

	def test_install_adds_builtin_tools_before_any_model(self):
		self.assertIn(
			"frappe.flow.assistant.sync_builtin_assistant",
			frappe.get_hooks("after_install", app_name="frappe"),
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

	def test_sync_restores_the_system_assistant_but_never_a_user_owned_one(self):
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
			{"doctype": "Flow Knowledge Base", "title": "Assistant Knowledge"}
		).insert()
		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		# the desk may add knowledge
		doc.set("knowledge_bases", [{"knowledge_base": knowledge.name}])
		doc.save()
		doc.update(
			{
				"instructions": "stale instructions",
				"max_iterations": 3,
				"model": other_model.name,
				"enabled": 0,
			}
		)
		doc.set("tools", [{"tool": BUILTIN_TOOLS[0].name}])
		doc.save(ignore_permissions=True)

		sync_builtin_assistant(model=self.model.name)

		doc.reload()
		self.assertEqual(doc.instructions, ASSISTANT_INSTRUCTIONS)
		self.assertEqual(doc.max_iterations, ASSISTANT_MAX_ITERATIONS)
		self.assertEqual([row.tool for row in doc.tools], [tool.name for tool in BUILTIN_TOOLS])
		self.assertEqual([row.knowledge_base for row in doc.knowledge_bases], [knowledge.name])
		self.assertEqual((doc.model, doc.enabled), (other_model.name, 0))

		# a user who took it over (cleared is_system_generated) keeps their changes
		frappe.db.set_value(
			"Flow Agent", ASSISTANT_AGENT_TITLE, {"is_system_generated": 0, "instructions": "user customised"}
		)
		sync_builtin_assistant(model=self.model.name)
		self.assertEqual(
			frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_TITLE, "instructions"), "user customised"
		)

	def test_the_assistant_follows_every_app_skill_past_the_desk_cap(self):
		for hook in ("after_app_install", "after_app_uninstall"):
			self.assertIn(
				"frappe.flow.assistant.sync_assistant_skills", frappe.get_hooks(hook, app_name="frappe")
			)
		skills = AppSkills(self)
		names = [f"skill-{i:02d}" for i in range(MAX_SKILLS + 1)]
		folders = [skills.write(name) for name in names]

		sync_assistant_skills("myapp")
		doc = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertEqual([row.skill for row in doc.skills], names)

		# the desk may add a skill of its own
		house = frappe.get_doc(
			{
				"doctype": "Flow Skill",
				"title": "House Style",
				"description": "Any reply.",
				"instructions": "Be plain.",
			}
		).insert()
		doc.append("skills", {"skill": house.name})
		doc.save()
		for folder in folders:
			shutil.rmtree(folder)
		sync_assistant_skills("myapp")
		doc.reload()
		self.assertEqual([row.skill for row in doc.skills], [house.name])

	def test_a_new_model_replaces_only_one_the_assistant_lost(self):
		with patch("frappe.flow.assistant.assistant.sync_builtin_assistant") as sync:
			self.insert_model("Second Model")
		sync.assert_not_called()

		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "model", "Gone Model")
		third = self.insert_model("Third Model")
		self.assertEqual(frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_TITLE, "model"), third.name)

	def insert_model(self, title: str):
		return frappe.get_doc(
			{"doctype": "Flow Model", "title": title, "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
