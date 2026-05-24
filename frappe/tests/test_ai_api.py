# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.ai.api import resume_run, start_run
from frappe.ai.model import ChatResponse, Model, ToolCall
from frappe.ai.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase


def _model_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "AI Model",
		"title": "Test API Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent_doc(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Agent",
		"title": "Test API Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _final(text: str = "done") -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _ask_user(prompt: str, *, options: list[str] | None = None, call_id: str = "q1") -> ChatResponse:
	return ChatResponse(
		content=None,
		tool_calls=[
			ToolCall(id=call_id, name="ask_user", arguments={"prompt": prompt, "options": options or []})
		],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestStartRun(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_start_run_without_agent_runs_assistant(self):
		with patch.object(Model, "chat", return_value=_final("hello")):
			payload = start_run("hi")

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "hello")
		run = frappe.get_doc("AI Run", payload["name"])
		self.assertFalse(run.agent)

	def test_start_run_with_named_agent_links_to_agent(self):
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name)

		run = frappe.get_doc("AI Run", payload["name"])
		self.assertEqual(run.agent, self.agent.name)
		self.assertEqual(payload["status"], "Completed")

	def test_start_run_paused_returns_questions(self):
		with patch.object(Model, "chat", return_value=_ask_user("Which list?", options=["A", "B"])):
			payload = start_run("email the list", agent=self.agent.name)

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(len(payload["questions"]), 1)
		self.assertEqual(payload["questions"][0]["prompt"], "Which list?")
		self.assertEqual(payload["questions"][0]["key"], "q1")

	def test_start_run_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("")

	def test_start_run_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("   ")

	def test_start_run_unknown_agent_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", agent="does-not-exist")


class TestResumeRun(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _pause(self, agent: str | None = None) -> str:
		with patch.object(Model, "chat", return_value=_ask_user("Confirm?")):
			payload = start_run("do it", agent=agent)
		self.assertEqual(payload["status"], "Paused")
		return payload["name"]

	def test_resume_paused_named_agent_completes(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"q1": "yes"})

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "ok")

	def test_resume_paused_assistant_completes(self):
		run_name = self._pause(agent=None)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"q1": "yes"})

		self.assertEqual(payload["status"], "Completed")

	def test_resume_accepts_json_string_answers(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, json.dumps({"q1": "yes"}))

		self.assertEqual(payload["status"], "Completed")

	def test_resume_can_pause_again_with_new_questions(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_ask_user("Are you sure?", call_id="q2")):
			payload = resume_run(run_name, {"q1": "yes"})

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(payload["questions"][0]["key"], "q2")

	def test_resume_rejects_non_paused_run(self):
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name)

		with self.assertRaisesRegex(frappe.ValidationError, "Paused"):
			resume_run(payload["name"], {})

	def test_resume_rejects_unknown_run(self):
		with self.assertRaises(frappe.DoesNotExistError):
			resume_run("does-not-exist", {})

	def test_resume_rejects_invalid_answers_type(self):
		run_name = self._pause(agent=self.agent.name)

		with self.assertRaisesRegex(frappe.ValidationError, "JSON object"):
			resume_run(run_name, "not json")

	def test_resume_failure_marks_run_failed(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				resume_run(run_name, {"q1": "yes"})

		failed = frappe.get_doc("AI Run", run_name)
		self.assertEqual(failed.status, "Failed")
		self.assertIn("boom", failed.error)
