# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.ai.doctype.ai_session.ai_session import derive_title
from frappe.tests import IntegrationTestCase


class TestAISession(IntegrationTestCase):
	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "AI Model",
				"title": "Session Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Session Test Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_session_requires_agent(self):
		doc = frappe.get_doc({"doctype": "AI Session", "title": "chat 1"})

		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_session_can_be_created_without_title(self):
		doc = frappe.get_doc({"doctype": "AI Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		self.assertIsNone(doc.title)

	def test_session_agent_is_locked_after_creation(self):
		other_agent = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Other Session Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		doc = frappe.get_doc({"doctype": "AI Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		doc.agent = other_agent.name
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
