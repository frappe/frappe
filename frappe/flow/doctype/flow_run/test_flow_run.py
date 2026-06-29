# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase

from flow.flow.doctype.flow_run.flow_run import create_run, persist_result
from flow.lib.agent import Question, RunResult
from flow.lib.model import ToolCall


def _completed_result(output: str = "all done") -> RunResult:
	return RunResult(
		output=output,
		messages=[
			{"role": "user", "content": "hi"},
			{"role": "assistant", "content": output},
		],
		tool_calls=[],
		iterations=1,
		usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
	)


def _tooled_result() -> RunResult:
	return RunResult(
		output="emailed two customers",
		messages=[
			{"role": "user", "content": "email customers"},
			{
				"role": "assistant",
				"content": None,
				"tool_calls": [
					{"id": "c1", "type": "function", "function": {"name": "read", "arguments": "{}"}}
				],
			},
			{"role": "tool", "tool_call_id": "c1", "content": "[]"},
			{"role": "assistant", "content": "emailed two customers"},
		],
		tool_calls=[ToolCall(id="c1", name="read", arguments={"doctype": "Customer"})],
		iterations=2,
		usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
	)


def _paused_result() -> RunResult:
	question = Question(prompt="Approve `execute`?", options=["Approve", "Deny"], key="c1")
	return RunResult(
		output=None,
		messages=[
			{"role": "user", "content": "delete the records"},
			{
				"role": "assistant",
				"content": None,
				"tool_calls": [
					{"id": "c1", "type": "function", "function": {"name": "execute", "arguments": "{}"}}
				],
			},
		],
		tool_calls=[],
		iterations=1,
		usage={"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
		paused=True,
		questions=[question],
	)


def _make_agent() -> str:
	model = frappe.get_doc(
		{
			"doctype": "Flow Model",
			"title": "Run Test Model",
			"model_id": "openai/gpt-4o-mini",
			"enabled": 1,
		}
	).insert()
	return (
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Run Test Agent",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		)
		.insert()
		.name
	)


def _new_session(agent: str) -> str:
	return (
		frappe.get_doc({"doctype": "Flow Session", "agent": agent, "title": "test"})
		.insert(ignore_permissions=True)
		.name
	)


class TestFlowRunPersistence(IntegrationTestCase):
	def setUp(self):
		self.agent = _make_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_persist_completed_run_writes_transcript_to_session(self):
		session = _new_session(self.agent)
		doc = persist_result(_completed_result(), source="Manual", input="hi", session=session)

		self.assertEqual(doc.status, "Completed")
		self.assertEqual(doc.iterations, 1)
		self.assertEqual(doc.output, "all done")

		session_doc = frappe.get_doc("Flow Session", session)
		self.assertEqual(len(session_doc.messages), 2)
		self.assertEqual(session_doc.messages[0].role, "user")
		self.assertEqual(session_doc.messages[0].content, "hi")
		self.assertEqual(session_doc.messages[1].role, "assistant")
		self.assertEqual(session_doc.messages[1].run, doc.name)

	def test_persist_serializes_tool_calls_as_dicts(self):
		session = _new_session(self.agent)
		doc = persist_result(_tooled_result(), source="Manual", input="email customers", session=session)

		tool_calls = json.loads(doc.tool_calls)
		self.assertEqual(tool_calls, [{"id": "c1", "name": "read", "arguments": {"doctype": "Customer"}}])

	def test_persist_tooled_run_writes_all_messages_to_session(self):
		session = _new_session(self.agent)
		doc = persist_result(_tooled_result(), source="Manual", input="email customers", session=session)

		session_doc = frappe.get_doc("Flow Session", session)
		roles = [row.role for row in session_doc.messages]
		self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])
		# Tool result row records which assistant call it answers.
		tool_row = session_doc.messages[2]
		self.assertEqual(tool_row.tool_call_id, "c1")
		# Assistant row with tool calls stores them as JSON.
		assistant_row = session_doc.messages[1]
		self.assertEqual(json.loads(assistant_row.tool_calls)[0]["function"]["name"], "read")
		# All rows tagged with the producing run.
		self.assertTrue(all(row.run == doc.name for row in session_doc.messages))

	def test_persist_paused_run_stores_questions(self):
		session = _new_session(self.agent)
		doc = persist_result(_paused_result(), source="Manual", input="email the list", session=session)

		self.assertEqual(doc.status, "Paused")
		self.assertIsNone(doc.output)
		questions = json.loads(doc.questions)
		self.assertEqual(len(questions), 1)
		self.assertEqual(questions[0]["prompt"], "Approve `execute`?")
		self.assertEqual(questions[0]["options"], ["Approve", "Deny"])
		self.assertEqual(questions[0]["key"], "c1")

	def test_apply_result_clears_questions_when_resumed(self):
		session = _new_session(self.agent)
		doc = persist_result(_paused_result(), source="Manual", input="email the list", session=session)
		self.assertTrue(doc.questions)

		doc.apply_result(_completed_result("emailed"))

		self.assertEqual(doc.status, "Completed")
		self.assertIsNone(doc.questions)
		self.assertEqual(doc.output, "emailed")

	def test_resume_accumulates_iterations_and_usage(self):
		session = _new_session(self.agent)
		doc = persist_result(_paused_result(), source="Manual", input="delete the records", session=session)
		self.assertEqual(doc.iterations, 1)
		self.assertEqual(json.loads(doc.usage)["total_tokens"], 6)

		doc.apply_result(_completed_result("emailed"))

		# A resumed run continues the same row: counts span both segments.
		self.assertEqual(doc.iterations, 2)
		self.assertEqual(
			json.loads(doc.usage), {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11}
		)

	def test_persist_records_usage(self):
		session = _new_session(self.agent)
		doc = persist_result(_tooled_result(), source="Manual", input="x", session=session)

		self.assertEqual(
			json.loads(doc.usage), {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
		)

	def test_create_run_with_config_snapshot(self):
		session = _new_session(self.agent)
		snapshot = {"instructions": "be terse", "tool_slugs": ["read", "execute"]}
		doc = create_run(source="Manual", input="hi", session=session, config_snapshot=snapshot)

		self.assertEqual(json.loads(doc.config_snapshot), snapshot)
		self.assertEqual(doc.status, "Running")

	def test_mark_failed_sets_status_and_error(self):
		session = _new_session(self.agent)
		doc = create_run(source="Manual", input="hi", session=session)

		doc.mark_failed("something broke")

		self.assertEqual(doc.status, "Failed")
		self.assertEqual(doc.error, "something broke")

	def test_mark_failed_truncates_long_error(self):
		session = _new_session(self.agent)
		doc = create_run(source="Manual", input="hi", session=session)

		doc.mark_failed("x" * 10000)

		self.assertEqual(len(doc.error), 5000)


class TestFlowRunValidation(IntegrationTestCase):
	def setUp(self):
		self.agent = _make_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_session_is_required(self):
		doc = frappe.get_doc({"doctype": "Flow Run", "source": "Manual", "status": "Running"})
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_paused_without_questions_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Manual", "status": "Paused", "session": session}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Paused"):
			doc.insert(ignore_permissions=True)

	def test_failed_without_error_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Manual", "status": "Failed", "session": session}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Failed"):
			doc.insert(ignore_permissions=True)

	def test_invalid_source_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Bogus", "status": "Running", "session": session}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_invalid_json_field_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{
				"doctype": "Flow Run",
				"source": "Manual",
				"status": "Running",
				"session": session,
				"tool_calls": "{not valid json",
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "JSON"):
			doc.insert(ignore_permissions=True)
