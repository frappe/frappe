# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow import Agent, ToolContext, tool
from frappe.flow.assistant import ASSISTANT_AGENT_NAME, ASSISTANT_AGENT_TITLE, sync_builtin_assistant
from frappe.flow.daemon.callback import tool_callback
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.knowledge import Knowledge
from frappe.flow.lib.agent import _ensure_tool, sync_agents, sync_tools
from frappe.flow.tests.test_fake_daemon import FakeDaemon
from frappe.flow.tools.builtins import read_records, sync_builtin_tools
from frappe.model.rename_doc import rename_doc
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


@tool(name="count_todos")
def count_open_todos(*, ctx: ToolContext) -> int:
	"""Count open ToDo records."""
	return frappe.db.count("ToDo", {"status": "Open"})


@tool(name="read_records")
def read_todos(*, ctx: ToolContext) -> list[str]:
	"""Read ToDo records."""
	return frappe.get_all("ToDo", pluck="name")


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


def broken_agents() -> list[Agent]:
	"""Two agents an app defines wrongly, and one it defines right."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")

	@tool
	def nested(*, ctx: ToolContext) -> str:
		"""Not importable."""
		return "x"

	lookup = Agent(name="Orphan Lookup", model=model, instructions="The sub-agent.")
	return [
		Agent(name="Nested Tool", model=model, instructions="Use it.", tools=[nested]),
		Agent(
			name="Missing Skill",
			model=model,
			instructions="Skilled.",
			skills=["missing"],
			sub_agents=[lookup],
		),
		Agent(name="Hooked Helper", model=model, instructions="From the hook.", tools=[count_todos]),
	]


def failing_agents() -> list[Agent]:
	"""An entry that fails before it returns any agent."""
	raise frappe.ValidationError("No model to run on.")


def clashing_agents() -> list[Agent]:
	"""Two agents whose tools share a name, and one whose tools do not."""
	model = frappe.db.get_value("Flow Model", {"title": MODEL}, "name")
	return [
		Agent(name="Two Counters", model=model, instructions="Count.", tools=[count_todos, count_open_todos]),
		Agent(name="Two Readers", model=model, instructions="Read.", tools=[read_todos, read_records]),
		Agent(name="Hooked Helper", model=model, instructions="From the hook.", tools=[count_todos]),
	]


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
		self.started = frappe.utils.now()

	def tearDown(self):
		frappe.db.rollback()

	def skipped(self, *titles: str) -> list[tuple[str, str]]:
		"""The Error Logs this test's syncs wrote under these titles, as sorted (title, reason) pairs.
		They live in the log database, which a rollback does not undo."""
		filters = {"method": ["in", titles], "creation": [">=", self.started]}
		return sorted(
			tuple(log) for log in frappe.get_all("Error Log", filters, ["method", "error"], as_list=True)
		)

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
		self.assertEqual(agent.name, "frappe/Todo Helper")  # after the app whose code builds it
		self.assertFalse(frappe.db.exists("Flow Agent", agent.name))
		self.assertFalse(frappe.db.exists("Flow Tool", "frappe/count_todos"))
		with self.assertRaises(frappe.DoesNotExistError):
			agent.run("hi")

		agent.sync()

		doc = frappe.get_doc("Flow Agent", agent.name)
		self.assertEqual(
			(doc.title, doc.app, doc.model, doc.instructions, doc.max_iterations, doc.enabled),
			("frappe/Todo Helper", "frappe", self.model.name, "Help with todos.", 7, 1),
		)
		self.assertEqual(doc.is_system_generated, 1)
		self.assertEqual(
			[row.tool for row in doc.tools],
			["frappe/count_todos", "frappe/close_todo", "frappe/read_records"],
		)
		close = frappe.get_doc("Flow Tool", "frappe/close_todo")
		self.assertEqual(
			(close.slug, close.title, close.type, close.import_path, close.description),
			("frappe/close_todo", "Close Todo", "Imported", f"{__name__}.close_todo", "Close a ToDo."),
		)
		self.assertEqual(
			(close.requires_confirmation, close.background, close.is_system_generated), (1, 1, 1)
		)
		self.assertEqual(frappe.db.get_value("Flow Tool", "frappe/count_todos", "requires_confirmation"), 0)
		self.assertTrue(frappe.db.get_value("Flow Tool", "frappe/read_records", "is_system_generated"))

	def test_sync_reapplies_the_definition_from_code(self):
		self.synced(max_iterations=7)
		other = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Other Code Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		frappe.db.set_value(
			"Flow Agent", "frappe/Todo Helper", {"instructions": "Stale.", "model": other.name, "enabled": 0}
		)
		frappe.db.set_value("Flow Tool", "frappe/count_todos", "description", "Stale.")

		# no max_iterations given: the code default comes back
		self.synced(instructions="Changed in code.", tools=[count_todos])

		doc = frappe.get_doc("Flow Agent", "frappe/Todo Helper")
		self.assertEqual(
			(doc.instructions, doc.max_iterations, [row.tool for row in doc.tools], doc.model, doc.enabled),
			("Changed in code.", 100, ["frappe/count_todos"], other.name, 0),
		)
		self.assertEqual(
			frappe.db.get_value("Flow Tool", "frappe/count_todos", "description"),
			"Count ToDo records with `status`.",
		)

	def test_sync_leaves_the_sites_agent_and_tool_of_the_same_name_alone(self):
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Todo Helper",
				"model": self.model.name,
				"instructions": "Owned in the Desk.",
			}
		).insert()
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

		self.synced()

		self.assertEqual(
			frappe.db.get_value("Flow Agent", "Todo Helper", ["instructions", "is_system_generated"]),
			("Owned in the Desk.", 0),
		)
		self.assertEqual(frappe.db.get_value("Flow Tool", "count_todos", "type"), "Script")
		self.assertEqual(
			frappe.db.get_value("Flow Agent", "frappe/Todo Helper", "instructions"), "Help with todos."
		)

		with self.subTest("an agent the site took over is left alone"):
			frappe.db.set_value("Flow Agent", "frappe/Todo Helper", "is_system_generated", 0)
			with self.assertRaisesRegex(frappe.ValidationError, "not owned by code"):
				self.synced()

	def test_two_apps_may_use_one_name(self):
		self.synced()
		theirs = self.agent(instructions="Theirs.")
		theirs.app, theirs.name = "other_app", "other_app/Todo Helper"
		theirs.sync()

		self.assertEqual(
			frappe.get_all(
				"Flow Agent",
				{"name": ["like", "%/Todo Helper"]},
				["name", "app", "instructions"],
				order_by="name",
			),
			[
				{"name": "frappe/Todo Helper", "app": "frappe", "instructions": "Help with todos."},
				{"name": "other_app/Todo Helper", "app": "other_app", "instructions": "Theirs."},
			],
		)

	def test_a_tool_moved_to_another_module_keeps_its_row(self):
		self.synced(tools=[count_todos])
		frappe.db.set_value("Flow Tool", "frappe/count_todos", "import_path", "frappe.gone.count_todos")

		self.assertEqual(_ensure_tool(count_todos), "frappe/count_todos")
		self.assertEqual(
			frappe.db.get_value("Flow Tool", "frappe/count_todos", "import_path"), f"{__name__}.count_todos"
		)

		with self.assertRaisesRegex(
			frappe.ValidationError, f"Tools {__name__}.count_todos and {__name__}.count_open_todos"
		):
			_ensure_tool(count_open_todos)

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

	def test_skills_are_the_apps_own_unless_named_with_their_app(self):
		self.assertEqual(
			self.agent(skills=["onboarding", "crm/onboarding"]).skills,
			["frappe/onboarding", "crm/onboarding"],
		)

	def test_sync_agents_writes_every_hooked_agent_once(self):
		with self.hooked("flow_agents", "hooked_agents"):
			sync_agents()
		doc = frappe.get_doc("Flow Agent", "frappe/Hooked Helper")
		self.assertEqual(
			(doc.instructions, doc.is_system_generated, [row.tool for row in doc.tools]),
			("From the hook.", 1, ["frappe/count_todos"]),
		)

		# a sub-agent may be hooked on its own as well
		with self.hooked("flow_agents", "shared_agents"):
			sync_agents()
		doc.reload()
		self.assertEqual([row.agent for row in doc.sub_agents], ["frappe/Hooked Lookup"])

	def test_migrate_keeps_the_first_agent_of_a_name(self):
		# one name declared twice: by an entry listed twice, or a sub-agent named like another agent
		with self.hooked("flow_agents", "hooked_agents", "hooked_agents"):
			sync_agents()
		with self.hooked("flow_agents", "conflicting_agents"):
			sync_agents()

		self.assertEqual(
			frappe.db.get_value("Flow Agent", "frappe/Hooked Lookup", "instructions"), "The sub-agent."
		)
		self.assertEqual(
			self.skipped(
				"Flow Agent frappe/Hooked Helper skipped", "Flow Agent frappe/Hooked Lookup skipped"
			),
			[
				(
					"Flow Agent frappe/Hooked Helper skipped",
					"Flow Agent frappe/Hooked Helper is declared more than once.",
				),
				(
					"Flow Agent frappe/Hooked Lookup skipped",
					"Flow Agent frappe/Hooked Lookup is declared more than once.",
				),
			],
		)

	def test_migrate_skips_an_agent_it_cannot_write(self):
		with self.hooked("flow_agents", "failing_agents", "broken_agents"):
			sync_agents()

		# a skipped agent leaves nothing behind, its sub-agent included
		self.assertEqual(
			frappe.get_all(
				"Flow Agent",
				[["name", "like", "frappe/%"], ["name", "!=", ASSISTANT_AGENT_NAME]],
				pluck="name",
			),
			["frappe/Hooked Helper"],
		)
		self.assertEqual(
			self.skipped(
				f"Flow Agents of {__name__}.failing_agents skipped",
				"Flow Agent frappe/Nested Tool skipped",
				"Flow Agent frappe/Missing Skill skipped",
			),
			[
				("Flow Agent frappe/Missing Skill skipped", "Could not find Row #1: Skill: frappe/missing"),
				(
					"Flow Agent frappe/Nested Tool skipped",
					"Tool nested must be exported as a module-level attribute by an installed app.",
				),
				(f"Flow Agents of {__name__}.failing_agents skipped", "No model to run on."),
			],
		)

	def test_migrate_skips_a_tool_or_agent_whose_tool_names_clash(self):
		with self.hooked("flow_tools", "count_todos", "count_open_todos"):
			sync_tools()
		with self.hooked("flow_agents", "clashing_agents"):
			sync_agents()

		self.assertEqual(
			frappe.db.get_value("Flow Tool", "frappe/count_todos", "import_path"), f"{__name__}.count_todos"
		)
		self.assertEqual(
			frappe.get_all(
				"Flow Agent",
				[["name", "like", "frappe/%"], ["name", "!=", ASSISTANT_AGENT_NAME]],
				pluck="name",
			),
			["frappe/Hooked Helper"],
		)
		clash = (
			f"Tools {__name__}.count_todos and {__name__}.count_open_todos are both named count_todos. "
			"Name one differently with @tool(name=...)."
		)
		readers_clash = (
			f"Tools frappe.flow.tools.builtins.read_records and {__name__}.read_todos are both named "
			"read_records. Name one differently with @tool(name=...)."
		)
		self.assertEqual(
			self.skipped(
				f"Flow Tool {__name__}.count_open_todos skipped",
				"Flow Agent frappe/Two Counters skipped",
				"Flow Agent frappe/Two Readers skipped",
			),
			[
				("Flow Agent frappe/Two Counters skipped", clash),
				("Flow Agent frappe/Two Readers skipped", readers_clash),
				(f"Flow Tool {__name__}.count_open_todos skipped", clash),
			],
		)

	def test_sync_tools_writes_every_hooked_tool_for_desk_agents_to_attach(self):
		with self.hooked("flow_tools", "close_todo"):
			sync_tools()

		doc = frappe.get_doc("Flow Tool", "frappe/close_todo")
		self.assertEqual(
			(doc.type, doc.import_path, doc.requires_confirmation, doc.is_system_generated),
			("Imported", f"{__name__}.close_todo", 1, 1),
		)
		agent = {"title": "Desk Agent", "model": self.model.name, "instructions": "Mine to edit."}
		frappe.get_doc({"doctype": "Flow Agent", **agent, "tools": [{"tool": "frappe/close_todo"}]}).insert()

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
		self.assertEqual([row.agent for row in doc.sub_agents], ["frappe/Todo Lookup"])
		self.assertIn("frappe/search_knowledge", [row.tool for row in doc.tools])
		self.assertIn("frappe/subagent", [row.tool for row in doc.tools])
		child = frappe.get_doc("Flow Agent", "frappe/Todo Lookup")
		self.assertEqual((child.description, child.is_system_generated), ("finds todos", 1))

	def test_runs_on_the_flow_server_which_calls_its_code_tools_back(self):
		agent = self.synced(auto_approve=True)

		session = agent.new_session(title="Todos")
		run = agent.run("how many?")

		self.assertEqual(
			(session.agent, session.title, session.auto_approve), ("frappe/Todo Helper", "Todos", 1)
		)
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

	def test_the_patch_names_the_rows_apps_shipped_after_their_app(self):
		from frappe.patches.v17_0.name_flow_app_rows_after_their_app import execute

		# as the syncs wrote them before
		sync_builtin_assistant(self.model.name)
		for doctype, name, old_name in (
			("Flow Tool", "frappe/read_records", "read_records"),
			("Flow Tool", "frappe/load_skill", "load_skill"),
			("Flow Agent", ASSISTANT_AGENT_NAME, ASSISTANT_AGENT_TITLE),
		):
			rename_doc(
				doctype, name, old_name, force=True, validate=False, show_alert=False, rebuild_search=False
			)
		frappe.db.set_value("Flow Agent", ASSISTANT_AGENT_TITLE, "app", None)
		frappe.get_doc(
			{
				"doctype": "Flow Skill",
				"title": "close-todos",
				"app": "frappe",
				"description": "Close overdue ToDos.",
				"instructions": "Close each one.",
				"is_system_generated": 1,
			}
		).insert(ignore_permissions=True, set_name="close-todos")
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"slug": "count_todos",
				"title": "Count Todos",
				"type": "Imported",
				"import_path": f"{__name__}.count_todos",
				"description": "Count ToDo records with `status`.",
				"is_system_generated": 1,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Hooked Helper",
				"model": self.model.name,
				"instructions": "From the hook.",
				"is_system_generated": 1,
				"tools": [{"tool": "count_todos"}, {"tool": "read_records"}, {"tool": "load_skill"}],
				"skills": [{"skill": "close-todos"}],
			}
		).insert(ignore_permissions=True)
		session = frappe.get_doc({"doctype": "Flow Session", "agent": "Hooked Helper"}).insert()
		desk = {"doctype": "Flow Agent", "model": self.model.name, "instructions": "Mine."}
		boss = frappe.get_doc({**desk, "title": "Boss", "sub_agents": [{"agent": "Hooked Helper"}]}).insert()
		slashed = frappe.get_doc({**desk, "title": "Sales/Support"})
		slashed.name = "Sales/Support"
		slashed.db_insert()

		with self.hooked("flow_agents", "hooked_agents"):
			execute()
			execute()  # a second run changes nothing

		helper = frappe.get_doc("Flow Agent", "frappe/Hooked Helper")
		self.assertEqual((helper.title, helper.app), ("frappe/Hooked Helper", "frappe"))
		self.assertEqual(
			[row.tool for row in helper.tools],
			["frappe/count_todos", "frappe/read_records", "frappe/load_skill"],
		)
		self.assertEqual([row.skill for row in helper.skills], ["frappe/close-todos"])
		self.assertEqual(frappe.db.get_value("Flow Tool", "frappe/count_todos", "slug"), "frappe/count_todos")
		self.assertEqual(
			frappe.db.get_value("Flow Skill", "frappe/close-todos", "title"), "frappe/close-todos"
		)
		self.assertEqual(frappe.db.get_value("Flow Session", session.name, "agent"), helper.name)
		self.assertEqual([row.agent for row in boss.reload().sub_agents], [helper.name])
		self.assertEqual(frappe.db.get_value("Flow Agent", "Sales-Support", "title"), "Sales-Support")
		self.assertFalse(frappe.db.exists("Flow Agent", "Sales/Support"))
		self.assertEqual(
			frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_NAME, ["title", "app"]),
			(ASSISTANT_AGENT_NAME, "frappe"),
		)
		self.assertIn(
			"frappe/load_skill",
			frappe.get_all("Flow Agent Tool", {"parent": ASSISTANT_AGENT_NAME}, pluck="tool"),
		)

		sync_builtin_assistant(self.model.name)
		with self.hooked("flow_agents", "hooked_agents"):
			sync_agents()
		for doctype, filters in (
			("Flow Agent", {"name": ["like", "%Hooked Helper"]}),
			("Flow Agent", {"name": ["like", f"%{ASSISTANT_AGENT_TITLE}"]}),
			("Flow Tool", {"name": ["like", "%count_todos"]}),
			("Flow Tool", {"name": ["like", "%read_records"]}),
		):
			self.assertEqual(frappe.db.count(doctype, filters), 1)
