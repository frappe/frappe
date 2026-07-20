# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.memory import store
from flow.memory.memory import build_memory_block, save_memory
from flow.tools.builtins import sync_builtin_tools

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _memory(agent: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent Memory",
		"agent": agent,
		"scope": "Agent",
		"content": "Widget A maps to item code WGT-001.",
	}
	doc.update(overrides)
	return doc


class IntegrationTestFlowAgentMemory(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		# LanceDB writes aren't covered by the tx rollback below; reset the (test-only) index.
		store.drop_table()
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Memory Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Memory Test Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"enabled": 1,
				"tools": [{"tool": "update_memory"}],
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()
		store.drop_table()

	def test_agent_scope_clears_user(self):
		doc = frappe.get_doc(_memory(self.agent.name, user="Administrator")).insert()
		self.assertIsNone(doc.user)

	def test_user_scope_requires_user(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(_memory(self.agent.name, scope="User")).insert()

	def test_content_length_capped(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(_memory(self.agent.name, content="x" * 501)).insert()

	def test_save_memory_adds_agent_scope(self):
		result = save_memory(self.agent.name, content="Acme bills to Mumbai branch.", scope="agent")
		doc = frappe.get_doc("Flow Agent Memory", result["memory_id"])
		self.assertEqual(result["action"], "added")
		self.assertEqual(doc.scope, "Agent")
		self.assertIsNone(doc.user)
		self.assertEqual(doc.source, "Agent")

	def test_save_memory_stamps_session_user(self):
		result = save_memory(self.agent.name, content="Prefers INR.", scope="user")
		doc = frappe.get_doc("Flow Agent Memory", result["memory_id"])
		self.assertEqual(doc.scope, "User")
		self.assertEqual(doc.user, frappe.session.user)

	def test_keywords_persist_and_are_preserved_on_content_edit(self):
		added = save_memory(
			self.agent.name, content="GST rate for stationery is 12%.", scope="agent", keywords="pens paper"
		)
		self.assertEqual(
			frappe.db.get_value("Flow Agent Memory", added["memory_id"], "keywords"), "pens paper"
		)
		# A content-only edit must keep the existing keywords.
		save_memory(
			self.agent.name,
			content="GST rate for stationery is 18%.",
			scope="agent",
			memory_id=added["memory_id"],
		)
		self.assertEqual(
			frappe.db.get_value("Flow Agent Memory", added["memory_id"], "keywords"), "pens paper"
		)

	def test_keywords_make_memory_findable_by_synonym(self):
		# Content shares no token with the query; only the keywords bridge the gap.
		hit = save_memory(
			self.agent.name,
			content="GST rate for stationery is 12 percent.",
			scope="agent",
			keywords="pens paper pencils office supplies",
		)
		miss = save_memory(self.agent.name, content="Fiscal year starts in April.", scope="agent")
		found = store.search(
			"tax for pens and paper", agent=self.agent.name, user=frappe.session.user, limit=5
		)
		self.assertIn(hit["memory_id"], found)
		self.assertNotIn(miss["memory_id"], found)

	def test_save_memory_rejects_bad_scope(self):
		with self.assertRaises(frappe.ValidationError):
			save_memory(self.agent.name, content="fact", scope="global")

	def test_save_memory_updates_by_id(self):
		added = save_memory(self.agent.name, content="Old fact.", scope="agent")
		result = save_memory(
			self.agent.name, content="New fact.", scope="agent", memory_id=added["memory_id"]
		)
		self.assertEqual(result["action"], "updated")
		self.assertEqual(frappe.db.get_value("Flow Agent Memory", added["memory_id"], "content"), "New fact.")

	def test_update_cannot_change_scope(self):
		# A shared Agent memory must not be privatized by an edit passing scope="user".
		added = save_memory(self.agent.name, content="Widget A maps to WGT-001.", scope="agent")
		save_memory(
			self.agent.name, content="Widget A maps to WGT-002.", scope="user", memory_id=added["memory_id"]
		)
		doc = frappe.get_doc("Flow Agent Memory", added["memory_id"])
		self.assertEqual(doc.scope, "Agent")
		self.assertIsNone(doc.user)
		self.assertEqual(doc.content, "Widget A maps to WGT-002.")

	def test_update_rejects_other_agents_memory(self):
		other = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Other Memory Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"enabled": 1,
			}
		).insert()
		added = save_memory(self.agent.name, content="Mine.", scope="agent")
		with self.assertRaises(frappe.ValidationError):
			save_memory(other.name, content="Steal.", scope="agent", memory_id=added["memory_id"])

	def test_update_rejects_other_users_memory(self):
		doc = frappe.get_doc(
			_memory(self.agent.name, scope="User", user="test@example.com", content="Their fact.")
		).insert()
		with self.assertRaises(frappe.ValidationError):
			save_memory(self.agent.name, content="Mine now.", scope="user", memory_id=doc.name)

	def test_update_rejects_archived_memory(self):
		doc = frappe.get_doc(_memory(self.agent.name, status="Archived")).insert()
		with self.assertRaises(frappe.ValidationError):
			save_memory(self.agent.name, content="Revive.", scope="agent", memory_id=doc.name)

	def test_add_refuses_past_limit(self):
		with patch("flow.memory.memory.MAX_ACTIVE_MEMORIES", 1):
			save_memory(self.agent.name, content="First.", scope="agent")
			with self.assertRaises(frappe.ValidationError):
				save_memory(self.agent.name, content="Second.", scope="agent")

	def test_block_none_without_memory_tool(self):
		other = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "No Memory Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"enabled": 1,
			}
		).insert()
		frappe.get_doc(_memory(other.name)).insert()
		self.assertIsNone(build_memory_block(other.name))

	def test_block_none_without_memories(self):
		self.assertIsNone(build_memory_block(self.agent.name))

	def test_block_injects_all_under_cap(self):
		shared = save_memory(self.agent.name, content="Widget A maps to WGT-001.", scope="agent")
		personal = save_memory(self.agent.name, content="Prefers INR.", scope="user")
		frappe.get_doc(
			_memory(self.agent.name, scope="User", user="test@example.com", content="Hidden fact.")
		).insert()

		block = build_memory_block(self.agent.name)
		self.assertIn(f"[{shared['memory_id']}] Widget A maps to WGT-001.", block)
		self.assertIn(f"[{personal['memory_id']}] Prefers INR.", block)
		self.assertNotIn("Hidden fact.", block)
		self.assertIn("data, not instructions", block)

	def test_block_overflow_uses_search_and_recency(self):
		names = [
			save_memory(self.agent.name, content=f"Fact number {i}.", scope="agent")["memory_id"]
			for i in range(4)
		]
		with (
			patch("flow.memory.memory.INJECT_ALL_CAP", 2),
			patch("flow.memory.memory.RECENT_ALWAYS", 1),
			patch("flow.memory.memory.store.search", return_value=[names[0]]) as search,
		):
			block = build_memory_block(self.agent.name, query="fact zero")
		search.assert_called_once()
		self.assertIn(names[0], block)
		self.assertIn(names[3], block)  # most recent, always shown
		self.assertNotIn(names[1], block)
		self.assertIn("more exist", block)

	def test_block_overflow_degrades_to_recency(self):
		for i in range(4):
			save_memory(self.agent.name, content=f"Fact number {i}.", scope="agent")
		with (
			patch("flow.memory.memory.INJECT_ALL_CAP", 2),
			patch("flow.memory.memory.store.search", return_value=[]),
		):
			block = build_memory_block(self.agent.name, query="anything")
		self.assertIn("Fact number 3.", block)
		self.assertIn("Fact number 2.", block)
