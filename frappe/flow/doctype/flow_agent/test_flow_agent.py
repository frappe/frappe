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
		"doctype": "Flow Model",
		"title": "Test Agent Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
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


class TestFlowAgentDefaults(IntegrationTestCase):
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


class TestFlowAgentAssemble(IntegrationTestCase):
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

		self.assertEqual(runtime.max_iterations, 20)

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
		frappe.db.set_value("Flow Tool", "read", "enabled", 0)

		runtime = self.agent_doc.assemble()

		self.assertEqual(sorted(t.name for t in runtime.tools), ["describe", "execute"])


class TestFlowAgentKnowledgeSearch(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model_doc.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		self.kb = frappe.get_doc({"doctype": "Flow Knowledge Base", "title": "Agent KB"}).insert()

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

	def test_search_tool_auto_added_when_kb_bound_without_it(self):
		agent = frappe.get_doc(
			_agent(
				self.model_doc.name,
				tools=[{"tool": "read"}],
				knowledge_bases=[{"knowledge_base": self.kb.name}],
			)
		).insert()

		self.assertIn("search_knowledge", [row.tool for row in agent.tools])

	def test_search_tool_not_duplicated_when_already_present(self):
		agent = frappe.get_doc(
			_agent(
				self.model_doc.name,
				tools=[{"tool": "search_knowledge"}],
				knowledge_bases=[{"knowledge_base": self.kb.name}],
			)
		).insert()

		self.assertEqual([row.tool for row in agent.tools].count("search_knowledge"), 1)


class TestFlowAgentRun(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_run_produces_ai_run_linked_to_session_with_agent(self):
		with patch.object(Model, "chat", return_value=_final_response()):
			ai_run = self.agent_doc.run("hi")

		session = frappe.get_doc("Flow Session", ai_run.session)
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

		failed = frappe.get_last_doc("Flow Run", filters={"status": "Failed"})
		self.assertIn("boom", failed.error)


class TestFlowAgentModelPermission(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.allowed = frappe.get_doc(_model(title="Allowed Model")).insert()
		self.restricted = frappe.get_doc(_model(title="Restricted Model")).insert()
		self.agent_doc = frappe.get_doc(_agent(self.restricted.name)).insert()
		self.user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "model-perm@example.com",
				"first_name": "Model Perm",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _restrict_to(self, model_name: str):
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": self.user.name,
				"allow": "Flow Model",
				"for_value": model_name,
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=self.user.name)

	def test_user_restricted_to_other_model_is_blocked(self):
		self._restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)

		with self.assertRaises(frappe.PermissionError):
			self.agent_doc.assemble()

	def test_user_permitted_for_model_can_assemble(self):
		self._restrict_to(self.restricted.name)
		frappe.set_user(self.user.name)

		self.assertIsInstance(self.agent_doc.assemble(), Agent)

	def test_model_override_is_permission_checked(self):
		self._restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)

		# Overriding to a permitted model works; the agent's own restricted model stays blocked.
		self.assertIsInstance(self.agent_doc.assemble(model=self.allowed.name), Agent)
		with self.assertRaises(frappe.PermissionError):
			self.agent_doc.assemble()


class TestFlowAgentSystemGenerated(IntegrationTestCase):
	"""Desk edits can't break system-generated agents; the owning app (ignore_permissions) can."""

	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _agent(self):
		return frappe.get_doc(_agent(self.model_doc.name, is_system_generated=1)).insert()

	def test_cannot_delete_via_desk(self):
		agent = self._agent()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"):
			frappe.delete_doc("Flow Agent", agent.name)

	def test_delete_blocked_even_with_ignore_permissions(self):
		agent = self._agent()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"):
			frappe.delete_doc("Flow Agent", agent.name, ignore_permissions=True)

	def test_cannot_rename(self):
		agent = self._agent()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot rename system-generated"):
			frappe.rename_doc("Flow Agent", agent.name, "Renamed Agent")

	def test_cannot_unset_flag(self):
		agent = self._agent()
		agent.is_system_generated = 0
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot remove the system-generated flag"):
			agent.save()

	def test_instructions_stay_editable(self):
		agent = self._agent()
		agent.instructions = "Be verbose."
		agent.save()
		self.assertEqual(frappe.db.get_value("Flow Agent", agent.name, "instructions"), "Be verbose.")
