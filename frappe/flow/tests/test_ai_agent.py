# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow import Agent, ToolContext, tool
from frappe.flow.daemon.callback import tool_callback
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.knowledge import Knowledge
from frappe.flow.lib.agent import sync_agents, sync_tools
from frappe.flow.tests.test_fake_daemon import FakeDaemon
from frappe.flow.tools.builtins import read_records, sync_builtin_tools
from frappe.tests import IntegrationTestCase

MODEL = "Code Agent Model"


@tool
def count_todos(status: str = "Open", *, ctx: ToolContext) -> int:
	"""Count ToDo records with `status`."""
	return frappe.db.count("ToDo", {"status": status})


@tool(requires_confirmation=True, background=True)
def close_todo(name: str, *, ctx: ToolContext) -> str:
	"""Close a ToDo."""
	frappe.db.set_value("ToDo", name, "status", "Closed")
	return name


def hooked_agents() -> list[Agent]:
	"""What an app's `flow_agents` entry returns."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")
	return [Agent(name="Hooked Helper", model=model, instructions="From the hook.", tools=[count_todos])]


def conflicting_agents() -> list[Agent]:
	"""A hooked agent named like another hooked agent's sub-agent."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")
	lookup = Agent(name="Hooked Lookup", model=model, instructions="The sub-agent.")
	return [
		Agent(name="Hooked Helper", model=model, instructions="From the hook.", sub_agents=[lookup]),
		Agent(name="Hooked Lookup", model=model, instructions="Another agent."),
	]


def shared_agents() -> list[Agent]:
	"""A sub-agent hooked on its own as well."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")
	lookup = Agent(name="Hooked Lookup", model=model, instructions="The sub-agent.")
	helper = Agent(name="Hooked Helper", model=model, instructions="From the hook.", sub_agents=[lookup])
	return [helper, lookup]


class TestAgent(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
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
			"tools": [count_todos, close_todo, read_records],
		}
		return Agent(**{**fields, **overrides})

	def synced(self, **overrides) -> Agent:
		agent = self.agent(**overrides)
		agent.sync()
		return agent

	def hooked(self, hook: str, *functions: str):
		"""`hook` lists these functions of this module."""
		get_hooks = frappe.get_hooks

		def hooks(name=None, *args, **kwargs):
			if name == hook:
				return [f"{__name__}.{function}" for function in functions]
			return get_hooks(name, *args, **kwargs)

		return patch("frappe.get_hooks", side_effect=hooks)

	def test_sync_writes_a_locked_agent_and_its_tools(self):
		agent = self.agent(max_iterations=7)
		# constructing one writes nothing, so it cannot run yet
		self.assertFalse(frappe.db.exists("Flow Agent", "Todo Helper"))
		self.assertFalse(frappe.db.exists("Flow Tool", "count_todos"))
		with self.assertRaises(frappe.DoesNotExistError):
			agent.run("hi")

		agent.sync()

		doc = frappe.get_doc("Flow Agent", agent.name)
		self.assertEqual(
			(doc.model, doc.instructions, doc.max_iterations, doc.enabled, doc.is_system_generated),
			(self.model.name, "Help with todos.", 7, 1, 1),
		)
		self.assertEqual([row.tool for row in doc.tools], ["count_todos", "close_todo", "read_records"])
		close = frappe.get_doc("Flow Tool", "close_todo")
		self.assertEqual(
			(close.title, close.type, close.import_path, close.description, close.requires_confirmation),
			("Close Todo", "Imported", f"{__name__}.close_todo", "Close a ToDo.", 1),
		)
		self.assertEqual((close.background, close.is_system_generated), (1, 1))
		self.assertEqual(frappe.db.get_value("Flow Tool", "count_todos", "requires_confirmation"), 0)
		self.assertTrue(frappe.db.get_value("Flow Tool", "read_records", "is_system_generated"))

	def test_sync_reapplies_the_definition_from_code(self):
		self.synced(max_iterations=7)
		other = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Other Code Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		frappe.db.set_value(
			"Flow Agent", "Todo Helper", {"instructions": "Stale.", "model": other.name, "enabled": 0}
		)
		frappe.db.set_value("Flow Tool", "count_todos", "description", "Stale.")

		# no max_iterations given: the code default comes back
		self.synced(instructions="Changed in code.", tools=[count_todos])

		doc = frappe.get_doc("Flow Agent", "Todo Helper")
		self.assertEqual(
			(doc.instructions, doc.max_iterations, [row.tool for row in doc.tools], doc.model, doc.enabled),
			("Changed in code.", 100, ["count_todos"], other.name, 0),
		)
		self.assertEqual(
			frappe.db.get_value("Flow Tool", "count_todos", "description"),
			"Count ToDo records with `status`.",
		)

	def test_sync_refuses_to_take_over_a_users_agent_or_tool(self):
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
			self.synced(name="Todo Counter")
		self.assertFalse(frappe.db.exists("Flow Agent", "Todo Counter"))

	def test_sync_refuses_a_tool_it_cannot_import(self):
		@tool
		def inner(*, ctx: ToolContext) -> str:
			"""Nested."""
			return "x"

		anonymous = tool(lambda *, ctx: "x", name="anonymous", description="Anonymous.")
		for unimportable in (inner, anonymous):
			with (
				self.subTest(unimportable.name),
				self.assertRaisesRegex(frappe.ValidationError, "module-level"),
			):
				self.synced(tools=[unimportable])

	def test_sync_agents_writes_every_hooked_agent_once(self):
		# one name declared twice: by an entry listed twice, or a sub-agent named like another agent
		for functions in (("hooked_agents", "hooked_agents"), ("conflicting_agents",)):
			with self.subTest(functions):
				with (
					self.hooked("flow_agents", *functions),
					self.assertRaisesRegex(frappe.ValidationError, "declared more than once"),
				):
					sync_agents()
				self.assertFalse(frappe.db.exists("Flow Agent", "Hooked Helper"))

		with self.hooked("flow_agents", "hooked_agents"):
			sync_agents()
		doc = frappe.get_doc("Flow Agent", "Hooked Helper")
		self.assertEqual(
			(doc.instructions, doc.is_system_generated, [row.tool for row in doc.tools]),
			("From the hook.", 1, ["count_todos"]),
		)

		# a sub-agent may be hooked on its own as well
		with self.hooked("flow_agents", "shared_agents"):
			sync_agents()
		doc.reload()
		self.assertEqual([row.agent for row in doc.sub_agents], ["Hooked Lookup"])

	def test_sync_tools_writes_every_hooked_tool_for_desk_agents_to_attach(self):
		with self.hooked("flow_tools", "close_todo"):
			sync_tools()

		doc = frappe.get_doc("Flow Tool", "close_todo")
		self.assertEqual(
			(doc.type, doc.import_path, doc.requires_confirmation, doc.is_system_generated),
			("Imported", f"{__name__}.close_todo", 1, 1),
		)
		agent = {"title": "Desk Agent", "model": self.model.name, "instructions": "Mine to edit."}
		frappe.get_doc({"doctype": "Flow Agent", **agent, "tools": [{"tool": "close_todo"}]}).insert()

	def test_sync_binds_knowledge_bases_and_sub_agents(self):
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		kb = Knowledge("Code Agent KB")
		lookup = Agent(
			name="Todo Lookup",
			model=self.model.name,
			instructions="Find todos.",
			description="finds todos",
			tools=[count_todos],
		)

		agent = self.synced(knowledge=kb, sub_agents=[lookup])

		doc = frappe.get_doc("Flow Agent", agent.name)
		self.assertEqual([row.knowledge_base for row in doc.knowledge_bases], [kb.name])
		self.assertEqual([row.agent for row in doc.sub_agents], ["Todo Lookup"])
		self.assertIn("search_knowledge", [row.tool for row in doc.tools])
		self.assertIn("subagent", [row.tool for row in doc.tools])
		child = frappe.get_doc("Flow Agent", "Todo Lookup")
		self.assertEqual((child.description, child.is_system_generated), ("finds todos", 1))

	def test_runs_on_the_flow_server_which_calls_its_code_tools_back(self):
		agent = self.synced(auto_approve=True)

		session = agent.new_session(title="Todos")
		run = agent.run("how many?")

		self.assertEqual((session.agent, session.title, session.auto_approve), ("Todo Helper", "Todos", 1))
		self.assertEqual((run.status, run.input), ("Running", "how many?"))
		self.assertNotEqual(run.session, session.name)
		config = self.daemon.configs[run.session]
		self.assertEqual(
			[client_tool["function"]["name"] for client_tool in config["client_tools"]],
			["count_todos", "close_todo", "read_records"],
		)
		self.assertEqual((config["confirm_tools"], config["auto_approve"]), (["close_todo"], True))

		# the callback runs a code tool as the session's owner
		reply = tool_callback(session_id=session.name, tool="count_todos", args={"status": "Open"})

		self.assertEqual((reply["is_error"], reply["content"].isdigit()), (False, True))
		self.assertEqual(frappe.session.user, "Administrator")
