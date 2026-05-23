# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.ai.agent import Question, RunResult
from frappe.ai.doctype.ai_run.ai_run import create_run, persist_result
from frappe.ai.model import ToolCall
from frappe.tests import IntegrationTestCase


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
				"tool_calls": [{"id": "c1", "type": "function", "function": {"name": "query", "arguments": "{}"}}],
			},
			{"role": "tool", "tool_call_id": "c1", "content": "[]"},
			{"role": "assistant", "content": "emailed two customers"},
		],
		tool_calls=[ToolCall(id="c1", name="query", arguments={"doctype": "Customer"})],
		iterations=2,
		usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
	)


def _paused_result() -> RunResult:
	question = Question(prompt="Which list?", options=["Customers", "Leads"], key="c1")
	return RunResult(
		output=None,
		messages=[
			{"role": "user", "content": "email the list"},
			{
				"role": "assistant",
				"content": None,
				"tool_calls": [{"id": "c1", "type": "function", "function": {"name": "ask_user", "arguments": "{}"}}],
			},
		],
		tool_calls=[],
		iterations=1,
		usage={"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
		paused=True,
		questions=[question],
	)


class TestAIRunPersistence(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_persist_completed_run_writes_transcript(self):
		doc = persist_result(_completed_result(), source="Manual", input="hi")

		self.assertEqual(doc.status, "Completed")
		self.assertEqual(doc.iterations, 1)
		self.assertEqual(doc.output, "all done")
		messages = json.loads(doc.messages)
		self.assertEqual(messages[0], {"role": "user", "content": "hi"})

	def test_persist_serializes_tool_calls_as_dicts(self):
		doc = persist_result(_tooled_result(), source="Manual", input="email customers")

		tool_calls = json.loads(doc.tool_calls)
		self.assertEqual(tool_calls, [{"id": "c1", "name": "query", "arguments": {"doctype": "Customer"}}])

	def test_persist_ephemeral_run_has_empty_agent(self):
		doc = persist_result(_completed_result(), source="Manual", input="hi")

		self.assertFalse(doc.agent)

	def test_persist_paused_run_stores_questions(self):
		doc = persist_result(_paused_result(), source="Manual", input="email the list")

		self.assertEqual(doc.status, "Paused")
		self.assertIsNone(doc.output)
		questions = json.loads(doc.questions)
		self.assertEqual(len(questions), 1)
		self.assertEqual(questions[0]["prompt"], "Which list?")
		self.assertEqual(questions[0]["options"], ["Customers", "Leads"])
		self.assertEqual(questions[0]["key"], "c1")

	def test_apply_result_clears_questions_when_resumed(self):
		doc = persist_result(_paused_result(), source="Manual", input="email the list")
		self.assertTrue(doc.questions)

		doc.apply_result(_completed_result("emailed"))

		self.assertEqual(doc.status, "Completed")
		self.assertIsNone(doc.questions)
		self.assertEqual(doc.output, "emailed")

	def test_persist_records_usage(self):
		doc = persist_result(_tooled_result(), source="Manual", input="x")

		self.assertEqual(json.loads(doc.usage), {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})

	def test_create_run_with_config_snapshot(self):
		snapshot = {"instructions": "be terse", "tool_slugs": ["query", "execute"]}
		doc = create_run(source="Manual", input="hi", config_snapshot=snapshot)

		self.assertEqual(json.loads(doc.config_snapshot), snapshot)
		self.assertEqual(doc.status, "Running")

	def test_mark_failed_sets_status_and_error(self):
		doc = create_run(source="Manual", input="hi")

		doc.mark_failed("something broke")

		self.assertEqual(doc.status, "Failed")
		self.assertEqual(doc.error, "something broke")

	def test_mark_failed_truncates_long_error(self):
		doc = create_run(source="Manual", input="hi")

		doc.mark_failed("x" * 10000)

		self.assertEqual(len(doc.error), 5000)


class TestAIRunValidation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_paused_without_questions_rejected(self):
		doc = frappe.get_doc({"doctype": "AI Run", "source": "Manual", "status": "Paused"})
		with self.assertRaisesRegex(frappe.ValidationError, "Paused"):
			doc.insert(ignore_permissions=True)

	def test_failed_without_error_rejected(self):
		doc = frappe.get_doc({"doctype": "AI Run", "source": "Manual", "status": "Failed"})
		with self.assertRaisesRegex(frappe.ValidationError, "Failed"):
			doc.insert(ignore_permissions=True)

	def test_invalid_source_rejected(self):
		doc = frappe.get_doc({"doctype": "AI Run", "source": "Bogus", "status": "Running"})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_invalid_json_field_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "AI Run",
				"source": "Manual",
				"status": "Running",
				"messages": "{not valid json",
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "JSON"):
			doc.insert(ignore_permissions=True)

