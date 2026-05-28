# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.ai.api import start_run
from frappe.ai.model import ChatResponse, Model, ToolCall
from frappe.ai.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase


def _ok(content: str = "done") -> ChatResponse:
	return ChatResponse(
		content=content,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _ask_user_call() -> ChatResponse:
	return ChatResponse(
		content=None,
		tool_calls=[ToolCall(id="c1", name="ask_user", arguments={"prompt": "Confirm?"})],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestStartRunSessions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model_doc = frappe.get_doc(
			{
				"doctype": "AI Model",
				"title": "Test Session Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_start_run_without_session_creates_new_session(self):
		with patch.object(Model, "chat", return_value=_ok()):
			result = start_run("hello world")

		self.assertIsNotNone(result["session"])
		session = frappe.get_doc("AI Session", result["session"])
		self.assertEqual(session.owner, frappe.session.user)
		self.assertEqual(session.title, "hello world")

	def test_start_run_links_run_to_session(self):
		with patch.object(Model, "chat", return_value=_ok()):
			result = start_run("hi")

		run = frappe.get_doc("AI Run", result["name"])
		self.assertEqual(run.session, result["session"])

	def test_second_turn_threads_prior_messages(self):
		captured: list[list[dict[str, Any]]] = []

		def capture_chat(messages: list[dict[str, Any]], **_: Any) -> ChatResponse:
			captured.append([dict(m) for m in messages])
			return _ok(f"reply {len(captured)}")

		with patch.object(Model, "chat", side_effect=capture_chat):
			first = start_run("what is 2+2")
			start_run("and what about 3+3", session=first["session"])

		second_messages = captured[1]
		# Second turn must contain the first user message, the first assistant reply,
		# and the new user message.
		user_msgs = [m for m in second_messages if m.get("role") == "user"]
		self.assertEqual([m["content"] for m in user_msgs], ["what is 2+2", "and what about 3+3"])
		assistant_msgs = [m for m in second_messages if m.get("role") == "assistant"]
		self.assertTrue(any(m.get("content") == "reply 1" for m in assistant_msgs))

	def test_explicit_session_id_reuses_it(self):
		from frappe.ai.assistant import sync_builtin_assistant

		sync_builtin_assistant(model=self.model_doc.name)
		session = frappe.get_doc({"doctype": "AI Session", "agent": "Assistant", "title": "carried"}).insert(
			ignore_permissions=True
		)

		with patch.object(Model, "chat", return_value=_ok()):
			result = start_run("hi", session=session.name)

		self.assertEqual(result["session"], session.name)

	def test_unknown_session_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", session="ghost-session-id")

	def test_agent_mismatch_with_session_raises(self):
		agent_a = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Agent Mismatch A",
				"model": self.model_doc.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		agent_b = frappe.get_doc(
			{
				"doctype": "AI Agent",
				"title": "Agent Mismatch B",
				"model": self.model_doc.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		session = frappe.get_doc({"doctype": "AI Session", "agent": agent_a.name}).insert(
			ignore_permissions=True
		)

		with self.assertRaisesRegex(frappe.ValidationError, "Agent Mismatch"):
			start_run("hi", session=session.name, agent=agent_b.name)

	def test_paused_session_blocks_new_turn(self):
		with patch.object(Model, "chat", return_value=_ask_user_call()):
			first = start_run("delete everything")

		self.assertEqual(first["status"], "Paused")

		# A new turn on the same session must error: caller should resume_run instead.
		with patch.object(Model, "chat", return_value=_ok()):
			with self.assertRaisesRegex(frappe.ValidationError, "paused"):
				start_run("nevermind", session=first["session"])


class TestStartRunSecurity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model_doc = frappe.get_doc(
			{
				"doctype": "AI Model",
				"title": "Test Security Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.other_user = _ensure_user("other-ai-user@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_session_owned_by_other_user_is_rejected(self):
		# Create session as the other user.
		frappe.set_user(self.other_user)
		with patch.object(Model, "chat", return_value=_ok()):
			theirs = start_run("private chat")
		frappe.set_user("Administrator")

		# Administrator is a System Manager so explicit perm check should let them through;
		# but for an ordinary user we must block. Verify the block path.
		frappe.set_user(_ensure_user("third-ai-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			start_run("steal context", session=theirs["session"])


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
