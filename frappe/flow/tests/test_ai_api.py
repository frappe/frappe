# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any

import frappe
from frappe.tests import IntegrationTestCase

from flow.api import attach_file, submit_feedback
from flow.memory import store as memory_store
from flow.tools.builtins import sync_builtin_tools


def _model_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test API Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent_doc(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
		"title": "Test API Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


class TestAttachFile(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _file(self, file_name: str = "report.txt", content: str = "report body"):
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
		).insert()

	def test_attach_file_returns_chip_metadata_and_stages_text(self):
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import staged_attachment

		file_doc = self._file()
		chip = attach_file(file_doc.name)

		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(chip["file_name"], "report.txt")
		self.assertNotIn("extracted_text", chip)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "report body")

	def test_attach_file_strips_and_resolves_input(self):
		file_doc = self._file()
		chip = attach_file(f"  {file_doc.name}  ")
		self.assertEqual(chip["file"], file_doc.name)

	def test_attach_file_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("")

	def test_attach_file_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("   ")

	def test_attach_file_unsupported_type_surfaces_at_upload(self):
		file_doc = self._file(file_name="data.bin", content="x")
		with self.assertRaisesRegex(frappe.ValidationError, "Unsupported file type"):
			attach_file(file_doc.name)


def _ensure_user(email: str) -> str:
	if frappe.db.exists("User", email):
		return email
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"enabled": 1,
		}
	)
	user.insert(ignore_permissions=True)
	return email


class TestSubmitFeedback(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Feedback Test Model")).insert()
		self.agent = frappe.get_doc(
			_agent_doc(self.model.name, title="Feedback Test Agent", tools=[{"tool": "update_memory"}])
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		memory_store.drop_table()

	def _run(self, status: str = "Completed", agent: str | None = None, **fields) -> str:
		session = frappe.get_doc({"doctype": "Flow Session", "agent": agent or self.agent.name}).insert(
			ignore_permissions=True
		)
		return (
			frappe.get_doc(
				{
					"doctype": "Flow Run",
					"session": session.name,
					"source": "Manual",
					"status": status,
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_up_rating_persists(self):
		run = self._run()
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Up")

	def test_denied_run_is_finished(self):
		run = self._run(status="Denied")
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})

	def test_down_with_comment_persists(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Wrong item code.")
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual(doc.feedback_rating, "Down")
		self.assertEqual(doc.feedback_comment, "Wrong item code.")

	def test_rejects_invalid_rating(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rating"):
			submit_feedback(self._run(), "Sideways")

	def test_rejects_unfinished_run(self):
		with self.assertRaisesRegex(frappe.ValidationError, "finished"):
			submit_feedback(self._run(status="Running"), "Up")

	def test_rejects_overlong_comment(self):
		with self.assertRaisesRegex(frappe.ValidationError, "characters"):
			submit_feedback(self._run(), "Down", comment="x" * 501)

	def test_rejects_other_users_run(self):
		run = self._run()
		frappe.set_user(_ensure_user("feedback-other-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			submit_feedback(run, "Up")

	def test_down_comment_saved_as_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		memory = frappe.get_doc("Flow Agent Memory", result["memory"])
		self.assertEqual(memory.agent, self.agent.name)
		self.assertEqual(memory.scope, "Agent")
		self.assertEqual(memory.source, "Feedback")
		self.assertEqual(memory.source_run, run)
		self.assertEqual(memory.content, "Widget A maps to WGT-001.")

	def test_down_comment_without_memory_tool_records_but_skips_memory(self):
		other = frappe.get_doc(_agent_doc(self.model.name, title="Feedback No Memory Agent")).insert()
		run = self._run(agent=other.name)
		result = submit_feedback(run, "Down", comment="Fix it.")
		self.assertNotIn("memory", result)
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Down")
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": other.name}))

	def test_up_never_saves_memory(self):
		result = submit_feedback(self._run(), "Up", comment="Nice.")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_down_without_comment_saves_no_memory(self):
		result = submit_feedback(self._run(), "Down")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_none_clears_rating(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Not quite.")
		self.assertEqual(submit_feedback(run, "None"), {"rating": None})
		doc = frappe.get_doc("Flow Run", run)
		self.assertFalse(doc.feedback_rating)
		self.assertIsNone(doc.feedback_comment)

	def test_none_keeps_saved_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		submit_feedback(run, "None")
		self.assertTrue(frappe.db.exists("Flow Agent Memory", result["memory"]))
