# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.daemon.client import DaemonClient, DaemonError
from flow.tests.fake_daemon import FakeDaemon
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
		return next(t for t in agent.client_tools() if t.name == "search_knowledge")

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
	"""agent.run against a scripted flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_run_returns_a_running_run_in_a_session_with_the_agent(self):
		run = self.agent_doc.run("hi")

		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual((session.agent, session.source), (self.agent_doc.name, "Manual"))
		self.assertEqual((run.status, run.source, run.output, run.input), ("Running", "Manual", None, "hi"))
		self.assertFalse(self.daemon.configs[session.name]["auto_approve"])

	def test_trigger_run_creates_an_auto_approved_session(self):
		run = self.agent_doc.run("hi", source="Trigger")

		self.assertEqual(run.source, "Trigger")
		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual((session.source, session.auto_approve), ("Trigger", 1))
		self.assertTrue(self.daemon.configs[session.name]["auto_approve"])

	def test_run_continues_a_session_without_changing_its_approval_policy(self):
		first = self.agent_doc.run("hi")
		session = frappe.get_doc("Flow Session", first.session)
		session.sync()
		session.set_auto_approve(True)
		self.daemon.calls.clear()
		second = self.agent_doc.run("again", session=first.session)

		self.assertEqual((second.session, second.status, second.input), (first.session, "Running", "again"))
		self.assertEqual(frappe.db.count("Flow Run", {"session": first.session}), 2)
		self.assertFalse(any(call[0] == "patch_config" for call in self.daemon.calls))

	def test_run_refuses_another_agents_session(self):
		other = frappe.get_doc(_agent(self.model_doc.name, title="Other Run Agent")).insert()
		first = self.agent_doc.run("hi")

		with self.assertRaisesRegex(frappe.ValidationError, "bound to agent"):
			other.run("mine now", session=first.session)

	def test_run_leaves_no_run_when_the_server_refuses(self):
		before = frappe.db.count("Flow Run")
		with patch.object(self.daemon, "run", side_effect=DaemonError(400, "attachment 'x' not found")):
			with self.assertRaisesRegex(frappe.ValidationError, "400"):
				self.agent_doc.run("hi")

		self.assertEqual(frappe.db.count("Flow Run"), before)


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


class TestFlowAgentClientTools(IntegrationTestCase):
	"""The tools an agent sends to the flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(
			_agent(self.model_doc.name, tools=[{"tool": "read"}, {"tool": "execute"}])
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def names(self):
		return [tool.name for tool in self.agent_doc.client_tools()]

	def test_schemas_and_the_confirmation_list(self):
		config = self.agent_doc.client_tool_config()
		self.assertEqual([tool["function"]["name"] for tool in config["client_tools"]], ["read", "execute"])
		self.assertEqual(config["client_tools"][0]["type"], "function")
		self.assertIn("properties", config["client_tools"][0]["function"]["parameters"])
		self.assertEqual(config["confirm_tools"], ["execute"])

	def test_update_memory_never_travels_to_the_server(self):
		self.agent_doc.append("tools", {"tool": "update_memory"})
		self.agent_doc.save()
		self.assertEqual(self.names(), ["read", "execute"])

	def test_disabled_tools_stay_home(self):
		frappe.db.set_value("Flow Tool", "read", "enabled", 0)
		self.assertEqual(self.names(), ["execute"])
