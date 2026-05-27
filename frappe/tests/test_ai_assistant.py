# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any

import frappe
from frappe.ai.agent import Done, TextChunk
from frappe.ai.assistant import (
	ASSISTANT_INSTRUCTIONS,
	ASSISTANT_TOOLS,
	build_assistant,
	run_assistant,
)
from frappe.ai.doctype.ai_run.ai_run import Error, RunStarted
from frappe.ai.model import ChatResponse, ToolCall
from frappe.tests import IntegrationTestCase


class FakeModel:
	model_id = "fake/assistant"

	def __init__(self, responses: list[ChatResponse], streams: list[list[str]] | None = None):
		self._responses = list(responses)
		self._streams = list(streams) if streams is not None else [[r.content or ""] for r in responses]
		self.calls: list[dict[str, Any]] = []

	def chat(self, messages, tools=None, *, stream=False):
		self.calls.append({"messages": list(messages), "tools": tools, "stream": stream})
		if not self._responses:
			raise AssertionError("FakeModel ran out of scripted responses")
		response = self._responses.pop(0)
		text_parts = self._streams.pop(0) if self._streams else [response.content or ""]
		if stream:
			return _scripted_stream(text_parts, response)
		return response


def _scripted_stream(text_parts: list[str], response: ChatResponse):
	for part in text_parts:
		if part:
			yield part
	return response


def _final(text: str) -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> ChatResponse:
	return ChatResponse(
		content=None,
		tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestBuildAssistant(IntegrationTestCase):
	def test_has_three_primitives_plus_ask_user(self):
		agent = build_assistant(model=FakeModel([]))
		self.assertEqual(
			sorted(t.name for t in agent.tools),
			["ask_user", "execute", "introspect", "query"],
		)

	def test_uses_assistant_instructions(self):
		agent = build_assistant(model=FakeModel([]))
		self.assertEqual(agent.instructions, ASSISTANT_INSTRUCTIONS)

	def test_uses_builtin_tool_objects(self):
		agent = build_assistant(model=FakeModel([]))
		self.assertEqual(agent.tools, ASSISTANT_TOOLS)

	def test_missing_enabled_model_throws(self):
		frappe.db.set_value("AI Model", {"enabled": 1}, "enabled", 0)
		try:
			with self.assertRaisesRegex(frappe.ValidationError, "AI Model"):
				build_assistant()
		finally:
			frappe.db.rollback()


class TestRunAssistant(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_persists_a_completed_run(self):
		model = FakeModel([_final("done")])

		run = run_assistant("hi", model=model)

		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.source, "Manual")
		session = frappe.get_doc("AI Session", run.session)
		self.assertFalse(session.agent)
		self.assertEqual(run.output, "done")
		self.assertEqual(run.input, "hi")

	def test_snapshot_captures_instructions_and_tool_slugs(self):
		run = run_assistant("hi", model=FakeModel([_final("ok")]))

		snapshot = json.loads(run.config_snapshot)
		self.assertEqual(snapshot["instructions"], ASSISTANT_INSTRUCTIONS)
		self.assertEqual(
			sorted(snapshot["tools"]),
			["ask_user", "execute", "introspect", "query"],
		)
		self.assertEqual(snapshot["model_id"], "fake/assistant")

	def test_tool_loop_completes_and_writes_one_run(self):
		frappe.get_doc({"doctype": "ToDo", "description": "assistant loop probe"}).insert()
		model = FakeModel(
			[
				_tool_call("query", {"doctype": "ToDo", "filters": {"description": "assistant loop probe"}}),
				_final("found one todo"),
			]
		)

		before = frappe.db.count("AI Run")
		run = run_assistant("get the todos", model=model)
		after = frappe.db.count("AI Run")

		self.assertEqual(after - before, 1)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.output, "found one todo")
		tool_calls = json.loads(run.tool_calls)
		self.assertEqual(tool_calls[0]["name"], "query")

	def test_agent_exception_marks_run_failed_and_reraises(self):
		model = FakeModel([])

		with self.assertRaises(AssertionError):
			run_assistant("hi", model=model)

		failed = frappe.get_last_doc("AI Run")
		self.assertEqual(failed.status, "Failed")
		self.assertTrue(failed.error)

	def test_paused_run_is_persisted_as_paused(self):
		model = FakeModel(
			[_tool_call("ask_user", {"prompt": "Which list?", "options": ["Customers", "Leads"]})]
		)

		run = run_assistant("email the list", model=model)

		self.assertEqual(run.status, "Paused")
		questions = json.loads(run.questions)
		self.assertEqual(questions[0]["prompt"], "Which list?")


class TestRunAssistantStreaming(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_stream_emits_run_started_text_chunks_and_done(self):
		model = FakeModel([_final("hello world")], streams=[["hello ", "world"]])

		events = list(run_assistant("hi", model=model, stream=True))

		self.assertIsInstance(events[0], RunStarted)
		self.assertTrue(events[0].name.startswith("AI-RUN-") or events[0].name)
		texts = [e.text for e in events if isinstance(e, TextChunk)]
		self.assertEqual(texts, ["hello ", "world"])
		self.assertIsInstance(events[-1], Done)
		self.assertEqual(events[-1].result.output, "hello world")

	def test_stream_persists_completed_run(self):
		model = FakeModel([_final("done")])

		events = list(run_assistant("hi", model=model, stream=True))
		run_started = events[0]

		run = frappe.get_doc("AI Run", run_started.name)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.output, "done")

	def test_stream_persists_paused_run(self):
		model = FakeModel([_tool_call("ask_user", {"prompt": "Which?", "options": ["A", "B"]})])

		events = list(run_assistant("pick", model=model, stream=True))
		run_started = events[0]

		run = frappe.get_doc("AI Run", run_started.name)
		self.assertEqual(run.status, "Paused")
		self.assertEqual(json.loads(run.questions)[0]["prompt"], "Which?")

	def test_stream_failure_marks_failed_and_emits_error(self):
		model = FakeModel([])  # exhausts on first chat call

		events = list(run_assistant("hi", model=model, stream=True))

		self.assertIsInstance(events[0], RunStarted)
		self.assertIsInstance(events[-1], Error)
		run = frappe.get_doc("AI Run", events[0].name)
		self.assertEqual(run.status, "Failed")
		self.assertTrue(run.error)
