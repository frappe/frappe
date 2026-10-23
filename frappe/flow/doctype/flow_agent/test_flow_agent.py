# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import os
from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow import ToolContext
from frappe.flow.assistant.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant
from frappe.flow.daemon.client import DaemonClient, DaemonError
from frappe.flow.doctype.flow_agent.flow_agent import MAX_SKILLS
from frappe.flow.doctype.flow_skill.flow_skill import sync_skills
from frappe.flow.doctype.flow_skill.test_flow_skill import AppSkills
from frappe.flow.tests.test_fake_daemon import FakeDaemon
from frappe.flow.tools.builtins import bind_load_skill, sync_builtin_tools
from frappe.tests import IntegrationTestCase
from frappe.utils import today

CTX = ToolContext(session_id="test", agent="Test Agent", user="Administrator")


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


def _skill_row(title: str, **overrides: Any) -> str:
	"""Insert a Flow Skill and return its name."""
	doc = {
		"doctype": "Flow Skill",
		"title": title,
		"description": f"When to use {title}.",
		"instructions": f"Body of {title}.",
	}
	doc.update(overrides)
	return frappe.get_doc(doc).insert().name


class TestFlowAgentValidation(IntegrationTestCase):
	def setUp(self):
		self.model_doc = frappe.get_doc(_model()).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_invalid_settings_are_refused(self):
		agent = frappe.get_doc(_agent(self.model_doc.name)).insert()
		for field, value, error in (
			("max_iterations", 0, "Max Iterations"),
			("token_budget", -1, "Token Budget"),
			("sub_agents", [{"agent": agent.name}], "own sub-agent"),
		):
			agent.reload()
			agent.set(field, value)
			with self.subTest(field=field), self.assertRaisesRegex(frappe.ValidationError, error):
				agent.save()


class TestFlowAgentKnowledgeSearch(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model_doc.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		self.kb = frappe.get_doc({"doctype": "Flow Knowledge Base", "title": "Agent KB"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _search_tool(self, kbs, title="Test Agent"):
		agent = frappe.get_doc(
			_agent(
				self.model_doc.name,
				title=title,
				tools=[{"tool": "search_knowledge"}],
				knowledge_bases=[{"knowledge_base": kb} for kb in kbs],
			)
		).insert()
		return next(t for t in agent.client_tools() if t.name == "search_knowledge")

	def test_search_is_fixed_to_the_agents_knowledge_bases(self):
		tool = self._search_tool([self.kb.name])
		self.assertEqual(set(tool.parameters["properties"]), {"query"})
		with patch("frappe.flow.knowledge.retriever.retrieve", return_value=[]) as retrieve:
			tool(query="hello", ctx=CTX)
			with self.assertRaises(Exception):
				tool(query="hello", kbs=["Some Other KB"], ctx=CTX)
		retrieve.assert_called_once_with("hello", kbs=[self.kb.name])

		# no knowledge base bound: fails closed
		with self.assertRaises(frappe.ValidationError):
			self._search_tool([], title="Unbound Agent")(query="hello", ctx=CTX)

	def test_binding_a_knowledge_base_adds_the_search_tool_once(self):
		for title, tools, expected in (
			("Reader", ["read"], ["read", "search_knowledge"]),
			("Searcher", ["search_knowledge"], ["search_knowledge"]),
		):
			agent = frappe.get_doc(
				_agent(
					self.model_doc.name,
					title=title,
					tools=[{"tool": tool} for tool in tools],
					knowledge_bases=[{"knowledge_base": self.kb.name}],
				)
			).insert()
			with self.subTest(title=title):
				self.assertEqual([row.tool for row in agent.tools], expected)


class TestFlowAgentRun(IntegrationTestCase):
	"""agent.run against a scripted flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_a_new_run_starts_a_session_approved_by_its_source(self):
		for kwargs, source, auto_approve in (({}, "Manual", 0), ({"source": "Trigger"}, "Trigger", 1)):
			with self.subTest(source=source):
				run = self.agent_doc.run("hi", **kwargs)

				session = frappe.get_doc("Flow Session", run.session)
				self.assertEqual(
					(session.agent, session.source, session.auto_approve),
					(self.agent_doc.name, source, auto_approve),
				)
				self.assertEqual(
					(run.status, run.source, run.output, run.input), ("Running", source, None, "hi")
				)
				self.assertEqual(self.daemon.configs[session.name]["auto_approve"], bool(auto_approve))

	def test_a_run_continues_only_its_own_agents_session(self):
		first = self.agent_doc.run("hi")
		session = frappe.get_doc("Flow Session", first.session)
		session.sync()
		session.set_auto_approve(True)
		self.daemon.calls.clear()
		second = self.agent_doc.run("again", session=first.session)

		self.assertEqual((second.session, second.status, second.input), (first.session, "Running", "again"))
		self.assertEqual(frappe.db.count("Flow Run", {"session": first.session}), 2)
		self.assertFalse(any(call[0] == "patch_config" for call in self.daemon.calls))

		other = frappe.get_doc(_agent(self.model_doc.name, title="Other Run Agent")).insert()
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
		self.agent = frappe.get_doc(_agent(self.model_doc.name, is_system_generated=1)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_the_desk_cannot_change_a_system_generated_agent(self):
		sync_builtin_assistant(self.model_doc.name)
		for label, error, change in (
			(
				"delete",
				"Cannot delete system-generated",
				lambda: frappe.delete_doc("Flow Agent", self.agent.name),
			),
			(
				"rename",
				"Cannot rename system-generated",
				lambda: frappe.rename_doc("Flow Agent", self.agent.name, "Renamed Agent"),
			),
			(
				"the builtin assistant, even by the app",
				"Cannot delete system-generated",
				lambda: frappe.delete_doc("Flow Agent", ASSISTANT_AGENT_TITLE, ignore_permissions=True),
			),
		):
			with self.subTest(label), self.assertRaisesRegex(frappe.ValidationError, error):
				change()

		other = frappe.get_doc(_agent(self.model_doc.name, title="Other Agent")).insert()
		skill = _skill_row("Expense Approval")
		for field, value, error in (
			("is_system_generated", 0, "Cannot remove the system-generated flag"),
			("instructions", "Be verbose.", "Cannot change Instructions"),
			("description", "Finds things.", "Cannot change Description"),
			("tools", [{"tool": "read"}], "Cannot change Tools"),
			("skills", [{"skill": skill}], "Cannot change Skills"),
			("sub_agents", [{"agent": other.name}], "Cannot change Sub-agents"),
		):
			self.agent.reload()
			self.agent.set(field, value)
			with self.subTest(field=field), self.assertRaisesRegex(frappe.ValidationError, error):
				self.agent.save()

	def test_enabled_and_model_stay_editable_and_the_app_keeps_control(self):
		other = frappe.get_doc(_model(title="Other Agent Model")).insert()
		self.agent.update({"enabled": 0, "model": other.name})
		self.agent.save()
		self.assertEqual(
			frappe.db.get_value("Flow Agent", self.agent.name, ["enabled", "model"]), (0, other.name)
		)

		self.agent.instructions = "Be verbose."
		self.agent.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Flow Agent", self.agent.name, "instructions"), "Be verbose.")

		frappe.delete_doc("Flow Agent", self.agent.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Agent", self.agent.name))


class TestFlowAgentClientTools(IntegrationTestCase):
	"""The tools an agent sends to the flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent_doc = frappe.get_doc(
			_agent(self.model_doc.name, tools=[{"tool": "read_records"}, {"tool": "execute"}])
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_each_enabled_tool_travels_as_its_kind(self):
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"title": "Helpdesk Ticket",
				"slug": "helpdesk_ticket",
				"type": "Server",
				"description": "Fetch a ticket.",
				"is_system_generated": 1,
			}
		).insert()
		for slug in ("update_memory", "read", "grep", "subagent", "suggest_replies", "helpdesk_ticket"):
			self.agent_doc.append("tools", {"tool": slug})
		self.agent_doc.save()

		config = self.agent_doc.session_tool_config()
		self.assertEqual(
			[tool["function"]["name"] for tool in config["client_tools"]],
			["read_records", "execute", "update_memory"],
		)
		self.assertEqual(config["client_tools"][0]["type"], "function")
		self.assertIn("properties", config["client_tools"][0]["function"]["parameters"])
		self.assertEqual(config["confirm_tools"], ["execute"])
		self.assertEqual(
			(config["tools"], config["extension_tools"]),
			(["read", "grep", "subagent", "suggest_replies"], ["helpdesk_ticket"]),
		)
		self.assertIn("Use read, grep to inspect", config["system_prompt"])

		for slug in ("read_records", "grep", "helpdesk_ticket"):
			frappe.db.set_value("Flow Tool", slug, "enabled", 0)
		config = self.agent_doc.session_tool_config()
		self.assertEqual(
			[tool["function"]["name"] for tool in config["client_tools"]], ["execute", "update_memory"]
		)
		self.assertEqual(
			(config["tools"], config["extension_tools"]), (["read", "subagent", "suggest_replies"], [])
		)

		frappe.db.set_value("Flow Tool", "read", "enabled", 0)
		config = self.agent_doc.session_tool_config()
		self.assertEqual(config["tools"], ["subagent", "suggest_replies"])
		self.assertNotIn("APP SOURCE CODE", config["system_prompt"])

	def test_changing_tools_or_sub_agents_warns_that_existing_sessions_keep_theirs(self):
		other = frappe.get_doc(_agent(self.model_doc.name, title="Other Agent")).insert()
		with patch("frappe.msgprint") as msgprint:
			self.agent_doc.append("tools", {"tool": "subagent"})
			self.agent_doc.save()
		msgprint.assert_not_called()  # no session yet

		frappe.get_doc({"doctype": "Flow Session", "agent": self.agent_doc.name}).insert()
		with patch("frappe.msgprint") as msgprint:
			self.agent_doc.instructions = "Be verbose."
			self.agent_doc.save()
		msgprint.assert_not_called()  # the tool list stays as it was

		for field, row in (("tools", {"tool": "grep"}), ("sub_agents", {"agent": other.name})):
			with self.subTest(field=field), patch("frappe.msgprint") as msgprint:
				self.agent_doc.append(field, row)
				self.agent_doc.save()
				self.assertIn("Existing sessions", msgprint.call_args.args[0])


class TestFlowAgentSubAgents(IntegrationTestCase):
	"""The agents an agent may hand a task to, as the flow server's `subagents` entries."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
		self.model_doc = frappe.get_doc(_model()).insert()
		self.child = frappe.get_doc(
			_agent(
				self.model_doc.name,
				title="Lookup",
				description="Finds past tickets.\nFast.",
				max_iterations=3,
				tools=[{"tool": "read_records"}, {"tool": "execute"}, {"tool": "read"}],
			)
		).insert()
		self.agent_doc = frappe.get_doc(
			_agent(
				self.model_doc.name, tools=[{"tool": "read_records"}], sub_agents=[{"agent": self.child.name}]
			)
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_an_enabled_sub_agent_runs_on_its_own_config_as_itself(self):
		self.assertEqual([row.tool for row in self.agent_doc.tools], ["read_records", "subagent"])
		context = {"site": "s", "user": "u", "agent": self.agent_doc.name, "session": "S1"}
		[config] = self.agent_doc.subagent_configs("S1", context)
		self.assertEqual((config["name"], config["description"]), ("Lookup", "Finds past tickets. Fast."))
		self.assertEqual(config["model"], "openai/gpt-4o-mini")
		self.assertTrue(config["system_prompt"].startswith("Be terse."))
		self.assertIn("APP SOURCE CODE", config["system_prompt"])
		self.assertEqual((config["tools"], config["extension_tools"]), (["read"], []))
		self.assertEqual([t["function"]["name"] for t in config["client_tools"]], ["read_records", "execute"])
		self.assertEqual((config["confirm_tools"], config["max_turns"]), (["execute"], 3))
		self.assertEqual(config["user_context"], {**context, "agent": "Lookup"})

		self.child.db_set("enabled", 0)
		self.assertEqual(self.agent_doc.subagent_configs("S1", {}), [])

		off = frappe.get_doc(_model(title="Off Model", enabled=0)).insert()
		self.child.db_set({"enabled": 1, "model": off.name})
		with self.assertRaisesRegex(frappe.ValidationError, "Sub-agent Lookup runs on Flow Model"):
			self.agent_doc.subagent_configs("S1", {})


class TestFlowAgentAttachmentSearch(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(
			_agent(self.model_doc.name, tools=[{"tool": "search_attachments"}])
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _search_tool(self, session=None):
		return next(t for t in self.agent.client_tools(session) if t.name == "search_attachments")

	def test_search_is_scoped_to_the_session_and_names_the_file(self):
		with patch("frappe.flow.knowledge.retriever.retrieve_attachments") as retrieve:
			self.assertEqual(self._search_tool()(query="refund", ctx=CTX), [])
		retrieve.assert_not_called()

		session = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert()
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "old.txt", "content": "x", "is_private": 1}
		).insert()
		session.append(
			"attachments",
			{"file": file_doc.name, "file_name": "old.txt", "file_size": 1, "mode": "Retrieval"},
		)
		session.save()
		tool = self._search_tool(session.name)
		self.assertEqual(set(tool.parameters["properties"]), {"query"})
		hit = {"attachment": file_doc.name, "content": "EXCERPT", "score": 0.5}
		with patch("frappe.flow.knowledge.retriever.retrieve_attachments", return_value=[hit]) as retrieve:
			hits = tool(query="refund", ctx=CTX)
		retrieve.assert_called_once_with("refund", session=session.name)
		self.assertEqual(hits, [{"file": "old.txt", "content": "EXCERPT", "score": 0.5}])


class TestFlowAgentInstructions(IntegrationTestCase):
	"""Jinja tags in the instructions, filled in when a session starts."""

	def setUp(self):
		self.model_doc = frappe.get_doc(_model()).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_tags_are_filled_in_and_other_text_stays_as_written(self):
		cases = (
			(
				"Helping {{ full_name }} ({{ user }}) on {{ today }}.",
				f"Helping Ada Lovelace (instructions-user@example.com) on {today()}.",
			),
			("{% raw %}Dear {{ doc.customer_name }},{% endraw %}", "Dear {{ doc.customer_name }},"),
			("Answer using README.md", "Answer using README.md"),
			("Never touch obj.__dict__ in scripts.", "Never touch obj.__dict__ in scripts."),
		)
		agents = [
			frappe.get_doc(_agent(self.model_doc.name, title=f"Agent {i}", instructions=text)).insert()
			for i, (text, _rendered) in enumerate(cases)
		]
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "instructions-user@example.com",
				"first_name": "Ada",
				"last_name": "Lovelace",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		frappe.set_user("instructions-user@example.com")

		for agent, (text, rendered) in zip(agents, cases, strict=True):
			with self.subTest(instructions=text):
				self.assertEqual(agent.session_tool_config()["system_prompt"], rendered)

		# underscore attributes stay blocked
		agent = frappe.get_doc(_agent(self.model_doc.name, instructions="{{ user.__class__ }}"))
		self.assertNotIn("<class", agent.render_instructions())

	def test_instructions_that_cannot_be_filled_in_are_refused(self):
		for text, error in (
			("Helping {{ full_name", "Could not fill in the instructions"),
			("Dear {{ doc.customer_name }},", "'doc' is undefined"),
		):
			doc = frappe.get_doc(_agent(self.model_doc.name, instructions=text))
			with self.subTest(instructions=text), self.assertRaisesRegex(frappe.ValidationError, error):
				doc.insert()


class TestFlowAgentSkillIndex(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _bind(self, *titles: str) -> str:
		self.agent.set("skills", [{"skill": title} for title in titles])
		self.agent.save()
		return self.agent.skill_index()

	def test_the_index_lists_enabled_bound_skills_in_name_order(self):
		self.assertEqual(self.agent.skill_index(), "")
		for title in ("Zebra Care", "Apple Picking"):
			_skill_row(title)
		_skill_row("Retired Skill", enabled=0)

		index = self._bind("Zebra Care", "Apple Picking", "Retired Skill")
		self.assertIn("<available_skills>", index)
		self.assertIn("<name>Apple Picking</name>", index)
		self.assertIn("<description>When to use Apple Picking.</description>", index)
		self.assertNotIn("Body of Apple Picking.", index)
		self.assertLess(index.index("Apple Picking"), index.index("Zebra Care"))
		self.assertNotIn("Retired Skill", index)
		with self.subTest("every bound skill disabled"):
			self.assertEqual(self._bind("Retired Skill"), "")

	def test_a_description_becomes_one_escaped_line(self):
		for title, description, expected in (
			(
				"Expense Approval",
				"Reviews claims.\n\nUse it  for  receipts.",
				"<description>Reviews claims. Use it for receipts.</description>",
			),
			(
				"Manager's Sign-off",
				'Don\'t approve the "final" claim.',
				"""<description>Don't approve the "final" claim.</description>""",
			),
			(
				"Markup",
				"Closes </skill> early & opens <skill>.",
				"&lt;/skill&gt; early &amp; opens &lt;skill&gt;",
			),
		):
			_skill_row(title, description=description)
			index = self._bind(title)
			with self.subTest(title=title):
				self.assertIn(f"<name>{title}</name>", index)
				self.assertIn(expected, index)
		with self.subTest("markup cannot close the block early"):
			self.assertEqual(index.count("</skill>"), 1)

	def test_an_agent_binds_at_most_the_prompt_budget_of_skills(self):
		titles = [_skill_row(f"Skill {i:03d}") for i in range(MAX_SKILLS + 1)]
		with self.assertRaisesRegex(frappe.ValidationError, "at most 30 skills"):
			self._bind(*titles)
		with self.subTest("the cap itself is allowed"):
			self.agent.reload()
			self.assertEqual(self._bind(*titles[:MAX_SKILLS]).count("<skill>"), MAX_SKILLS)

	def test_a_global_skill_reaches_each_agent_carrying_the_tool_once(self):
		_skill_row("Retired Style", is_global=1, enabled=0)
		self.agent.append("tools", {"tool": "load_skill"})
		self.agent.save()
		with self.subTest("a disabled global skill stays out"):
			self.assertEqual(self.agent.skill_index(), "")

		_skill_row("House Style", is_global=1)
		self.assertIn("<name>House Style</name>", self.agent.skill_index())
		self.assertEqual(self._bind("House Style").count("<name>House Style</name>"), 1)
		toolless = frappe.get_doc(_agent(self.model_doc.name, title="Toolless Agent")).insert()
		self.assertEqual(toolless.skill_index(), "")


class TestFlowAgentInvocableSkills(IntegrationTestCase):
	"""What a user may start with /skill:<command>: bound and global skills flagged for it."""

	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_flagged_bound_and_global_skills_are_listed_with_their_command(self):
		_skill_row("Expense Approval", user_invocable=1)
		_skill_row("House Style", is_global=1, user_invocable=1)
		_skill_row("Model Only")
		with self.subTest("the tool is not needed to start a skill by hand"):
			self.assertEqual([row["name"] for row in self.agent.invocable_skills()], ["House Style"])
			self.assertEqual(self.agent.skill_index(), "")

		self.agent.set("skills", [{"skill": "Expense Approval"}, {"skill": "Model Only"}])
		self.agent.save()
		with self.subTest("bound and global"):
			self.assertEqual(
				[(row["name"], row["command"]) for row in self.agent.invocable_skills()],
				[("Expense Approval", "expense-approval"), ("House Style", "house-style")],
			)


class TestFlowAgentLoadSkill(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model_doc.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _tool(self, agent=None):
		agent = agent or self.agent
		return next((t for t in agent.client_tools() if t.name == "load_skill"), None)

	def _bind(self, *titles: str):
		self.agent.set("skills", [{"skill": t} for t in titles])
		self.agent.save()

	def test_a_bound_skill_loads_its_instructions_and_files(self):
		_skill_row("Expense Approval")
		self.assertEqual([row.tool for row in self.agent.tools], [])
		self._bind("Expense Approval")
		self.assertEqual([row.tool for row in self.agent.tools], ["load_skill"])
		tool = self._tool()
		self.assertEqual(set(tool.parameters["properties"]), {"name", "file"})
		self.assertEqual(tool(name="Expense Approval", ctx=CTX), "Body of Expense Approval.")

		with self.subTest("a file an app skill mentions"):
			folder = AppSkills(self).write("close-todos")
			with open(os.path.join(folder, "forms.md"), "w") as file:
				file.write("Form fields.")
			sync_skills()
			self._bind("close-todos")
			self.assertEqual(self._tool()(name="close-todos", file="forms.md", ctx=CTX), "Form fields.")

	def test_the_builtin_assistant_carries_the_tool_and_loads_a_global_skill(self):
		sync_builtin_assistant(self.model_doc.name)
		assistant = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertIn("load_skill", [row.tool for row in assistant.tools])
		_skill_row("House Style", is_global=1)
		self.assertEqual(self._tool(assistant)(name="House Style", ctx=CTX), "Body of House Style.")

	def test_a_skill_the_agent_cannot_see_is_refused(self):
		for title, enabled in (("Mine", 1), ("Theirs", 1), ("Retired", 0)):
			_skill_row(title, enabled=enabled)
		self._bind("Mine", "Retired")
		for label, load, error in (
			(
				"another agent's skill",
				lambda: self._tool()(name="Theirs", ctx=CTX),
				"No skill named Theirs. Available: Mine",
			),
			("a disabled skill", lambda: self._tool()(name="Retired", ctx=CTX), "No skill named Retired"),
			(
				"an unbound tool",
				lambda: bind_load_skill(None)(name="House Style", ctx=CTX),
				"Skills are not configured",
			),
		):
			with self.subTest(label), self.assertRaisesRegex(frappe.ValidationError, error):
				load()
