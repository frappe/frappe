# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from flow.ai.doctype.ai_session.ai_session import AISession, derive_title


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

	def test_session_can_be_created_without_agent(self):
		# Code-defined agents drive sessions without a doctype agent link.
		doc = frappe.get_doc({"doctype": "AI Session", "title": "chat 1"}).insert(ignore_permissions=True)

		self.assertIsNone(doc.agent)

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


class TestClearOldLogs(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _session_with_run(self, *, age_days: int) -> str:
		session = frappe.get_doc({"doctype": "AI Session", "title": "chat"})
		session.append("messages", {"role": "user", "content": "hi"})
		session.insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "AI Run", "session": session.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		old = frappe.utils.add_days(frappe.utils.now(), -age_days)
		frappe.db.set_value("AI Session", session.name, "modified", old, update_modified=False)
		return session.name, run.name

	def test_old_session_and_linked_run_and_messages_are_purged(self):
		old_session, old_run = self._session_with_run(age_days=100)

		AISession.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("AI Session", old_session))
		self.assertFalse(frappe.db.exists("AI Run", old_run))
		self.assertEqual(frappe.db.count("AI Session Message", {"parent": old_session}), 0)

	def test_recent_session_is_kept(self):
		recent_session, recent_run = self._session_with_run(age_days=1)

		AISession.clear_old_logs(days=30)

		self.assertTrue(frappe.db.exists("AI Session", recent_session))
		self.assertTrue(frappe.db.exists("AI Run", recent_run))


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
