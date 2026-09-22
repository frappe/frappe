# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow import Agent, tool
from flow.daemon.callback import tool_callback
from flow.daemon.client import DaemonClient
from flow.knowledge import Knowledge
from flow.lib.agent import sync_agents
from flow.tests.test_fake_daemon import FakeDaemon
from flow.tools.builtins import read, sync_builtin_tools

MODEL = "Code Agent Model"


@tool
def count_todos(status: str = "Open") -> int:
	"""Count ToDo records with `status`."""
	return frappe.db.count("ToDo", {"status": status})


@tool(requires_confirmation=True)
def close_todo(name: str) -> str:
	"""Close a ToDo."""
	frappe.db.set_value("ToDo", name, "status", "Closed")
	return name


def hooked_agents() -> list[Agent]:
	"""What an app's `flow_agents` entry returns."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")
	return [Agent(name="Hooked Helper", model=model, instructions="From the hook.", tools=[count_todos])]


class TestAgent(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model = frappe.get_doc(
			{"doctype": "Flow Model", "title": MODEL, "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def agent(self, **overrides) -> Agent:
		fields = {
			"name": "Todo Helper",
			"model": self.model.name,
			"instructions": "Help with todos.",
			"tools": [count_todos, close_todo, read],
		}
		return Agent(**{**fields, **overrides})

	def synced(self, **overrides) -> Agent:
		agent = self.agent(**overrides)
		agent.sync()
		return agent

	def test_constructing_an_agent_writes_nothing(self):
		self.agent()

		self.assertFalse(frappe.db.exists("Flow Agent", "Todo Helper"))
		self.assertFalse(frappe.db.exists("Flow Tool", "count_todos"))

	def test_running_an_unsynced_agent_fails(self):
		with self.assertRaises(frappe.DoesNotExistError):
			self.agent().run("hi")

	def test_sync_creates_a_locked_flow_agent(self):
		agent = self.synced(max_iterations=7)

		doc = frappe.get_doc("Flow Agent", agent.name)
		self.assertEqual(
			(doc.model, doc.instructions, doc.max_iterations, doc.enabled, doc.is_system_generated),
			(self.model.name, "Help with todos.", 7, 1, 1),
		)
		self.assertEqual([row.tool for row in doc.tools], ["count_todos", "close_todo", "read"])

	def test_sync_restores_the_code_default_max_iterations(self):
		self.synced(max_iterations=7)

		self.synced()

		self.assertEqual(frappe.db.get_value("Flow Agent", "Todo Helper", "max_iterations"), 50)

	def test_sync_refuses_to_take_over_a_user_owned_agent(self):
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Todo Helper",
				"model": self.model.name,
				"instructions": "Owned in the Desk.",
			}
		).insert()

		with self.assertRaisesRegex(frappe.ValidationError, "already exists"):
			self.synced()

		doc = frappe.get_doc("Flow Agent", "Todo Helper")
		self.assertEqual((doc.instructions, doc.is_system_generated), ("Owned in the Desk.", 0))

	def test_tools_become_locked_imported_flow_tools(self):
		self.synced()

		doc = frappe.get_doc("Flow Tool", "close_todo")
		self.assertEqual(
			(doc.title, doc.type, doc.import_path, doc.description, doc.requires_confirmation),
			("Close Todo", "Imported", f"{__name__}.close_todo", "Close a ToDo.", 1),
		)
		self.assertEqual(doc.is_system_generated, 1)
		self.assertEqual(frappe.db.get_value("Flow Tool", "count_todos", "requires_confirmation"), 0)
		self.assertTrue(frappe.db.get_value("Flow Tool", "read", "is_system_generated"))

	def test_sync_reapplies_the_definition_from_code(self):
		self.synced()
		other = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Other Code Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		frappe.db.set_value(
			"Flow Agent", "Todo Helper", {"instructions": "Stale.", "model": other.name, "enabled": 0}
		)
		frappe.db.set_value("Flow Tool", "count_todos", "description", "Stale.")

		self.synced(instructions="Changed in code.", tools=[count_todos], max_iterations=3)

		doc = frappe.get_doc("Flow Agent", "Todo Helper")
		self.assertEqual(
			(doc.instructions, doc.max_iterations, [row.tool for row in doc.tools], doc.model, doc.enabled),
			("Changed in code.", 3, ["count_todos"], other.name, 0),
		)
		self.assertEqual(
			frappe.db.get_value("Flow Tool", "count_todos", "description"),
			"Count ToDo records with `status`.",
		)

	def test_sync_agents_writes_every_hooked_agent(self):
		get_hooks = frappe.get_hooks

		def hooks(hook=None, *args, **kwargs):
			if hook == "flow_agents":
				return [f"{__name__}.hooked_agents"]
			return get_hooks(hook, *args, **kwargs)

		with patch("frappe.get_hooks", side_effect=hooks):
			sync_agents()

		doc = frappe.get_doc("Flow Agent", "Hooked Helper")
		self.assertEqual(
			(doc.instructions, doc.is_system_generated, [row.tool for row in doc.tools]),
			("From the hook.", 1, ["count_todos"]),
		)

	def test_sync_agents_refuses_duplicate_names_before_writing(self):
		get_hooks = frappe.get_hooks

		def hooks(hook=None, *args, **kwargs):
			if hook == "flow_agents":
				return [f"{__name__}.hooked_agents", f"{__name__}.hooked_agents"]
			return get_hooks(hook, *args, **kwargs)

		with (
			patch("frappe.get_hooks", side_effect=hooks),
			self.assertRaisesRegex(frappe.ValidationError, "declared more than once"),
		):
			sync_agents()

		self.assertFalse(frappe.db.exists("Flow Agent", "Hooked Helper"))

	def test_a_tool_slug_owned_by_another_definition_is_refused(self):
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"slug": "count_todos",
				"title": "Count",
				"type": "Script",
				"description": "Counts.",
				"code": "def main():\n\treturn 1",
			}
		).insert()

		with self.assertRaisesRegex(frappe.ValidationError, "different definition"):
			self.synced()
		self.assertFalse(frappe.db.exists("Flow Agent", "Todo Helper"))

	def test_a_nested_tool_is_refused(self):
		@tool
		def inner() -> str:
			"""Nested."""
			return "x"

		with self.assertRaisesRegex(frappe.ValidationError, "module-level"):
			self.synced(tools=[inner])

	def test_a_lambda_tool_is_refused(self):
		anonymous = tool(lambda: "x", name="anonymous", description="Anonymous.")

		with self.assertRaisesRegex(frappe.ValidationError, "module-level"):
			self.synced(tools=[anonymous])

	def test_knowledge_bases_are_bound(self):
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		kb = Knowledge("Code Agent KB")

		agent = self.synced(knowledge=kb)

		doc = frappe.get_doc("Flow Agent", agent.name)
		self.assertEqual([row.knowledge_base for row in doc.knowledge_bases], [kb.name])
		self.assertIn("search_knowledge", [row.tool for row in doc.tools])

	def test_new_session_and_run_go_through_the_flow_server(self):
		agent = self.synced(auto_approve=True)

		session = agent.new_session(title="Todos")
		run = agent.run("how many?")

		self.assertEqual((session.agent, session.title, session.auto_approve), ("Todo Helper", "Todos", 1))
		self.assertEqual((run.status, run.input), ("Running", "how many?"))
		self.assertNotEqual(run.session, session.name)
		config = self.daemon.configs[run.session]
		self.assertEqual(
			[client_tool["function"]["name"] for client_tool in config["client_tools"]],
			["count_todos", "close_todo", "read"],
		)
		self.assertEqual((config["confirm_tools"], config["auto_approve"]), (["close_todo"], True))

	def test_the_callback_runs_a_code_tool_as_the_session_owner(self):
		session = self.synced().new_session()

		reply = tool_callback(session_id=session.name, tool="count_todos", args={"status": "Open"})

		self.assertEqual((reply["is_error"], reply["content"].isdigit()), (False, True))
		self.assertEqual(frappe.session.user, "Administrator")
