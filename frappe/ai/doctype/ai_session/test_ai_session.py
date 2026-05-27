# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.ai.doctype.ai_session.ai_session import derive_title
from frappe.tests import IntegrationTestCase


class TestAISession(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_session_can_be_created_without_agent(self):
		doc = frappe.get_doc({"doctype": "AI Session", "title": "chat 1"}).insert(ignore_permissions=True)

		self.assertIsNone(doc.agent)
		self.assertEqual(doc.title, "chat 1")

	def test_session_can_be_created_without_title(self):
		doc = frappe.get_doc({"doctype": "AI Session"}).insert(ignore_permissions=True)

		self.assertIsNone(doc.title)

	def test_session_agent_is_locked_after_creation(self):
		model = frappe.get_doc(
			{
				"doctype": "AI Model",
				"title": "Lock Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		agent_a = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Agent A",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		agent_b = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Agent B",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()

		doc = frappe.get_doc({"doctype": "AI Session", "agent": agent_a.name}).insert(ignore_permissions=True)

		doc.agent = agent_b.name
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change the agent"):
			doc.save(ignore_permissions=True)


class TestDeriveTitle(IntegrationTestCase):
	def test_short_text_returned_as_is(self):
		self.assertEqual(derive_title("hello world"), "hello world")

	def test_long_text_truncated_with_ellipsis(self):
		long_input = "a" * 200
		result = derive_title(long_input)

		self.assertEqual(len(result), 80)
		self.assertTrue(result.endswith("…"))

	def test_whitespace_collapsed(self):
		self.assertEqual(derive_title("hello   \n  world"), "hello world")

	def test_empty_input_returns_empty_string(self):
		self.assertEqual(derive_title(""), "")
		self.assertEqual(derive_title(None), "")
