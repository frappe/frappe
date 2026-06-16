# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.lib.agent import Agent
from flow.lib.model import ChatResponse, Model
from flow.tools.builtins import sync_builtin_tools


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "AI Model",
		"title": "Test Agent Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Agent",
		"title": "Test Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"max_iterations": 5,
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _final_response() -> ChatResponse:
	return ChatResponse(
		content="done",
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestAIAgentDefaults(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_default_tools_populated_on_insert(self):
		doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

		self.assertEqual([row.tool for row in doc.tools], ["describe", "read", "execute"])

	def test_explicit_tools_override_defaults(self):
		doc = frappe.get_doc(_agent(self.model_doc.name, tools=[{"tool": "read"}])).insert()

		self.assertEqual([row.tool for row in doc.tools], ["read"])

	def test_zero_max_iterations_rejected(self):
		doc = frappe.get_doc(_agent(self.model_doc.name, max_iterations=0))
		with self.assertRaisesRegex(frappe.ValidationError, "Max Iterations"):
			doc.insert()

	def test_link_to_unknown_model_rejected(self):
		doc = frappe.get_doc(_agent("does-not-exist"))
		with self.assertRaises(frappe.LinkValidationError):
			doc.insert()


class TestAIAgentAssemble(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_assemble_returns_agent_with_resolved_tools(self):
		runtime = self.agent_doc.assemble()

		self.assertIsInstance(runtime, Agent)
		self.assertEqual(runtime.name, self.agent_doc.name)
		self.assertEqual(runtime.instructions, "Be terse.")
		self.assertEqual(sorted(t.name for t in runtime.tools), ["describe", "execute", "read"])
		self.assertEqual(runtime.max_iterations, 5)

	def test_assemble_uses_default_iterations_when_unset(self):
		self.agent_doc.max_iterations = None
		self.agent_doc.save()

		runtime = self.agent_doc.assemble()

		self.assertEqual(runtime.max_iterations, 10)

	def test_assemble_throws_when_agent_disabled(self):
		self.agent_doc.enabled = 0
		self.agent_doc.save()

		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.agent_doc.assemble()

	def test_assemble_throws_when_model_disabled(self):
		self.model_doc.enabled = 0
		self.model_doc.save()

		with self.assertRaisesRegex(frappe.ValidationError, "Model"):
			self.agent_doc.assemble()

	def test_assemble_skips_disabled_tools(self):
		frappe.db.set_value("AI Tool", "read", "enabled", 0)

		runtime = self.agent_doc.assemble()

		self.assertEqual(sorted(t.name for t in runtime.tools), ["describe", "execute"])


class TestAIAgentKnowledgeSearch(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.kb = frappe.get_doc({"doctype": "AI Knowledge Base", "title": "Agent KB"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _search_tool(self, kbs):
		agent = frappe.get_doc(
			_agent(
				self.model_doc.name,
				tools=[{"tool": "search_knowledge"}],
				knowledge_bases=[{"knowledge_base": kb} for kb in kbs],
			)
		).insert()
		runtime = agent.assemble()
		return next(t for t in runtime.tools if t.name == "search_knowledge")

	def test_schema_exposes_only_query(self):
		tool = self._search_tool([self.kb.name])
		self.assertEqual(set(tool.parameters["properties"]), {"query"})

	def test_search_uses_agent_configured_kbs(self):
		tool = self._search_tool([self.kb.name])
		with patch("flow.knowledge.retriever.retrieve", return_value=[]) as mock:
			tool(query="hello")
		mock.assert_called_once_with("hello", kbs=[self.kb.name])

	def test_llm_supplied_kbs_are_rejected(self):
		tool = self._search_tool([self.kb.name])
		with patch("flow.knowledge.retriever.retrieve", return_value=[]) as mock:
			with self.assertRaises(Exception):
				tool(query="hello", kbs=["Some Other KB"])
		mock.assert_not_called()

	def test_search_without_configured_kbs_fails_closed(self):
		tool = self._search_tool([])
		with self.assertRaises(frappe.ValidationError):
			tool(query="hello")


class TestAIAgentRun(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_run_produces_ai_run_linked_to_session_with_agent(self):
		with patch.object(Model, "chat", return_value=_final_response()):
			ai_run = self.agent_doc.run("hi")

		session = frappe.get_doc("AI Session", ai_run.session)
		self.assertEqual(session.agent, self.agent_doc.name)
		self.assertEqual(ai_run.status, "Completed")
		self.assertEqual(ai_run.source, "Manual")
		self.assertEqual(ai_run.output, "done")
		self.assertEqual(ai_run.input, "hi")

	def test_run_records_config_snapshot(self):
		import json

		with patch.object(Model, "chat", return_value=_final_response()):
			ai_run = self.agent_doc.run("hi")

		snapshot = json.loads(ai_run.config_snapshot)
		self.assertEqual(snapshot["title"], "Test Agent")
		self.assertEqual(snapshot["model"], self.model_doc.name)
		self.assertEqual(sorted(snapshot["tools"]), ["describe", "execute", "read"])
		self.assertEqual(snapshot["max_iterations"], 5)

	def test_run_accepts_source_param(self):
		with patch.object(Model, "chat", return_value=_final_response()):
			ai_run = self.agent_doc.run("hi", source="Trigger")

		self.assertEqual(ai_run.source, "Trigger")

	def test_run_marks_failed_and_reraises_on_exception(self):
		with patch.object(Model, "chat", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				self.agent_doc.run("hi")

		failed = frappe.get_last_doc("AI Run", filters={"status": "Failed"})
		self.assertIn("boom", failed.error)
