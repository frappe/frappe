# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any
from unittest.mock import patch

from werkzeug.wrappers import Response

import frappe
from frappe.ai.api import resume_run, start_run
from frappe.ai.model import ChatResponse, Model, ToolCall
from frappe.ai.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase


def _scripted_stream(text_parts: list[str], response: ChatResponse):
	for part in text_parts:
		if part:
			yield part
	return response


def _stream_chat(text_parts: list[str], response: ChatResponse):
	"""Build a side_effect function that returns a stream when stream=True, else the response."""

	def chat(self, messages, tools=None, *, stream=False):
		if stream:
			return _scripted_stream(text_parts, response)
		return response

	return chat


def _sse_events(response: Response) -> list[dict[str, Any]]:
	"""Parse an SSE response body into a list of event dicts."""
	body = b"".join(response.iter_encoded()).decode()
	events = []
	for block in body.split("\n\n"):
		block = block.strip()
		if not block:
			continue
		data_lines = [line[6:] for line in block.split("\n") if line.startswith("data: ")]
		if data_lines:
			events.append(json.loads("\n".join(data_lines)))
	return events


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


def _confirm_call(call_id: str = "c1") -> ChatResponse:
	"""A response that calls the `execute` tool, which requires confirmation and so pauses the run."""
	return ChatResponse(
		content=None,
		tool_calls=[ToolCall(id=call_id, name="execute", arguments={"code": "result = 1"})],
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

	def test_start_run_without_agent_uses_default_assistant(self):
		from frappe.ai.assistant import ASSISTANT_AGENT_TITLE

		with patch.object(Model, "chat", return_value=_final("hello")):
			payload = start_run("hi")

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "hello")
		session = frappe.get_doc("AI Session", payload["session"])
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)

	def test_start_run_with_named_agent_links_to_agent(self):
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name)

		session = frappe.get_doc("AI Session", payload["session"])
		self.assertEqual(session.agent, self.agent.name)
		self.assertEqual(payload["status"], "Completed")

	def test_start_run_paused_returns_questions(self):
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("delete the records", agent=self.agent.name)

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(len(payload["questions"]), 1)
		self.assertEqual(payload["questions"][0]["options"], ["Approve", "Deny"])
		self.assertEqual(payload["questions"][0]["key"], "c1")

	def test_start_run_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("")

	def test_start_run_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("   ")

	def test_start_run_unknown_agent_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", agent="does-not-exist")

	def test_start_run_stream_returns_sse_response_with_event_sequence(self):
		with patch.object(Model, "chat", new=_stream_chat(["hello ", "world"], _final("hello world"))):
			response = start_run("hi", agent=self.agent.name, stream=True)
			self.assertIsInstance(response, Response)
			self.assertEqual(response.mimetype, "text/event-stream")
			events = _sse_events(response)

		types = [e["type"] for e in events]
		self.assertEqual(types[0], "run_started")
		self.assertEqual(types[-1], "done")
		text_deltas = [e["delta"] for e in events if e["type"] == "text"]
		self.assertEqual(text_deltas, ["hello ", "world"])

		done = events[-1]
		self.assertEqual(done["status"], "Completed")
		self.assertEqual(done["output"], "hello world")

		run = frappe.get_doc("AI Run", events[0]["name"])
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.output, "hello world")

	def test_start_run_stream_without_agent_uses_default_assistant(self):
		from frappe.ai.assistant import ASSISTANT_AGENT_TITLE

		with patch.object(Model, "chat", new=_stream_chat(["hi"], _final("hi"))):
			response = start_run("hello", stream=True)
			events = _sse_events(response)

		self.assertEqual(events[0]["type"], "run_started")
		run = frappe.get_doc("AI Run", events[0]["name"])
		session = frappe.get_doc("AI Session", run.session)
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)

	def test_start_run_stream_accepts_truthy_string(self):
		with patch.object(Model, "chat", new=_stream_chat(["ok"], _final("ok"))):
			response = start_run("hi", agent=self.agent.name, stream="true")
			self.assertIsInstance(response, Response)
			_sse_events(response)  # drain inside patch

	def test_start_run_stream_failure_emits_error_event(self):
		def boom(self, messages, tools=None, *, stream=False):
			raise RuntimeError("kaboom")

		with patch.object(Model, "chat", new=boom):
			response = start_run("hi", agent=self.agent.name, stream=True)
			events = _sse_events(response)

		self.assertEqual(events[0]["type"], "run_started")
		self.assertEqual(events[-1]["type"], "error")
		self.assertIn("kaboom", events[-1]["message"])

		run = frappe.get_doc("AI Run", events[0]["name"])
		self.assertEqual(run.status, "Failed")


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
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("do it", agent=agent)
		self.assertEqual(payload["status"], "Paused")
		return payload["name"]

	def test_resume_paused_named_agent_completes(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"c1": "Deny"})

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "ok")

	def test_resume_paused_assistant_completes(self):
		run_name = self._pause(agent=None)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"c1": "Deny"})

		self.assertEqual(payload["status"], "Completed")

	def test_resume_accepts_json_string_answers(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, json.dumps({"c1": "Deny"}))

		self.assertEqual(payload["status"], "Completed")

	def test_resume_can_pause_again_with_new_questions(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_confirm_call(call_id="c2")):
			payload = resume_run(run_name, {"c1": "Deny"})

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(payload["questions"][0]["key"], "c2")

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

	def test_resume_stream_returns_sse_response(self):
		# pause first via non-streaming start
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("do it", agent=self.agent.name)
		run_name = payload["name"]

		with patch.object(Model, "chat", new=_stream_chat(["ok"], _final("ok"))):
			response = resume_run(run_name, {"c1": "Deny"}, stream=True)
			self.assertIsInstance(response, Response)
			events = _sse_events(response)

		types = [e["type"] for e in events]
		self.assertIn("run_started", types)
		self.assertIn("done", types)
		self.assertEqual(events[-1]["status"], "Completed")

		run = frappe.get_doc("AI Run", run_name)
		self.assertEqual(run.status, "Completed")

	def test_resume_failure_marks_run_failed(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				resume_run(run_name, {"c1": "Deny"})

		failed = frappe.get_doc("AI Run", run_name)
		self.assertEqual(failed.status, "Failed")
		self.assertIn("boom", failed.error)
