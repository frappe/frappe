# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.daemon.client import DaemonClient, DaemonError
from flow.flow.doctype.flow_agent.flow_agent import MAX_SKILLS
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


class TestFlowAgentDefaults(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.model_doc = frappe.get_doc(_model()).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_tools_are_exactly_those_given(self):
		bare = frappe.get_doc(_agent(self.model_doc.name)).insert()
		reader = frappe.get_doc(
			_agent(self.model_doc.name, title="Reader", tools=[{"tool": "read"}])
		).insert()

		self.assertEqual(
			([row.tool for row in bare.tools], [row.tool for row in reader.tools]), ([], ["read"])
		)

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

	def test_definition_is_locked_for_the_desk(self):
		agent = self._agent()
		agent.instructions = "Be verbose."
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Instructions"):
			agent.save()
		agent.reload()
		agent.append("tools", {"tool": "read"})
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Tools"):
			agent.save()
		agent.reload()
		agent.append("skills", {"skill": _skill_row("Expense Approval")})
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Skills"):
			agent.save()

	def test_enabled_and_model_stay_editable(self):
		agent = self._agent()
		other = frappe.get_doc(_model(title="Other Agent Model")).insert()
		agent.update({"enabled": 0, "model": other.name})
		agent.save()
		self.assertEqual(frappe.db.get_value("Flow Agent", agent.name, ["enabled", "model"]), (0, other.name))

	def test_owning_app_can_change_the_definition(self):
		agent = self._agent()
		agent.instructions = "Be verbose."
		agent.save(ignore_permissions=True)
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

	def test_update_memory_travels_to_the_server(self):
		self.agent_doc.append("tools", {"tool": "update_memory"})
		self.agent_doc.save()
		self.assertEqual(self.names(), ["read", "execute", "update_memory"])

	def test_disabled_tools_stay_home(self):
		frappe.db.set_value("Flow Tool", "read", "enabled", 0)
		self.assertEqual(self.names(), ["execute"])

	def test_server_tools_are_selected_without_becoming_callback_tools(self):
		self.agent_doc.append("tools", {"tool": "read_file"})
		self.agent_doc.append("tools", {"tool": "grep"})
		self.agent_doc.save()

		self.assertEqual(self.agent_doc.server_tools(), ["read_file", "grep"])
		self.assertEqual(self.names(), ["read", "execute"])
		config = self.agent_doc.session_tool_config()
		self.assertEqual(config["tools"], ["read_file", "grep"])
		self.assertIn("APP SOURCE CODE", config["system_prompt"])

		frappe.db.set_value("Flow Tool", "grep", "enabled", 0)
		self.assertEqual(self.agent_doc.server_tools(), ["read_file"])
		frappe.db.set_value("Flow Tool", "read_file", "enabled", 0)
		config = self.agent_doc.session_tool_config()
		self.assertEqual(config["tools"], [])
		self.assertNotIn("APP SOURCE CODE", config["system_prompt"])

	def test_changing_the_tool_list_warns_that_existing_sessions_keep_theirs(self):
		frappe.get_doc({"doctype": "Flow Session", "agent": self.agent_doc.name}).insert()
		with patch("frappe.msgprint") as msgprint:
			self.agent_doc.append("tools", {"tool": "grep"})
			self.agent_doc.save()
		self.assertIn("Existing sessions", msgprint.call_args.args[0])

		# an edit that leaves the tool list alone has nothing to warn about
		with patch("frappe.msgprint") as msgprint:
			self.agent_doc.instructions = "Be verbose."
			self.agent_doc.save()
		msgprint.assert_not_called()

	def test_an_agent_without_sessions_is_changed_quietly(self):
		with patch("frappe.msgprint") as msgprint:
			self.agent_doc.append("tools", {"tool": "grep"})
			self.agent_doc.save()
		msgprint.assert_not_called()


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
		with patch("flow.knowledge.retriever.retrieve_attachments", return_value=[hit]) as retrieve:
			hits = tool(query="refund")
		retrieve.assert_called_once_with("refund", session=session.name)
		self.assertEqual(hits, [{"file": "old.txt", "content": "EXCERPT", "score": 0.5}])

	def test_search_without_a_session_finds_nothing(self):
		with patch("flow.knowledge.retriever.retrieve_attachments") as retrieve:
			self.assertEqual(self._search_tool()(query="refund"), [])
		retrieve.assert_not_called()


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

	def _carry_the_tool(self):
		self.agent.append("tools", {"tool": "load_skill"})
		self.agent.save()

	def test_an_agent_without_skills_has_an_empty_index(self):
		self.assertEqual(self.agent.skill_index(), "")

	def test_the_index_lists_each_bound_skill_by_name_and_description(self):
		_skill_row("Expense Approval")
		index = self._bind("Expense Approval")
		self.assertIn("<available_skills>", index)
		self.assertIn("<name>Expense Approval</name>", index)
		self.assertIn("<description>When to use Expense Approval.</description>", index)
		self.assertNotIn("Body of Expense Approval.", index)

	def test_skills_are_listed_in_name_order(self):
		for title in ("Zebra Care", "Apple Picking"):
			_skill_row(title)
		index = self._bind("Zebra Care", "Apple Picking")
		self.assertLess(index.index("Apple Picking"), index.index("Zebra Care"))

	def test_a_disabled_skill_is_left_out(self):
		_skill_row("Expense Approval")
		_skill_row("Retired Skill", enabled=0)
		index = self._bind("Expense Approval", "Retired Skill")
		self.assertIn("Expense Approval", index)
		self.assertNotIn("Retired Skill", index)

	def test_the_index_is_empty_when_every_bound_skill_is_disabled(self):
		_skill_row("Retired Skill", enabled=0)
		self.assertEqual(self._bind("Retired Skill"), "")

	def test_a_multiline_description_is_flattened_to_one_line(self):
		_skill_row("Expense Approval", description="Reviews claims.\n\nUse it  for  receipts.")
		index = self._bind("Expense Approval")
		self.assertIn("<description>Reviews claims. Use it for receipts.</description>", index)

	def test_markup_in_a_description_cannot_break_the_block(self):
		_skill_row("Expense Approval", description="Closes </skill> early & opens <skill>.")
		index = self._bind("Expense Approval")
		self.assertIn("&lt;/skill&gt; early &amp; opens &lt;skill&gt;", index)
		self.assertEqual(index.count("</skill>"), 1)

	def test_quotes_stay_literal_in_the_index(self):
		_skill_row("Manager's Sign-off", description='Don\'t approve the "final" claim.')
		index = self._bind("Manager's Sign-off")
		self.assertIn("<name>Manager's Sign-off</name>", index)
		self.assertIn("""<description>Don't approve the "final" claim.</description>""", index)

	def test_an_agent_cannot_bind_more_skills_than_the_prompt_budget(self):
		for i in range(MAX_SKILLS + 1):
			_skill_row(f"Skill {i:03d}")
		with self.assertRaisesRegex(frappe.ValidationError, "at most 30 skills"):
			self._bind(*[f"Skill {i:03d}" for i in range(MAX_SKILLS + 1)])

	def test_the_cap_itself_is_allowed(self):
		for i in range(MAX_SKILLS):
			_skill_row(f"Skill {i:03d}")
		index = self._bind(*[f"Skill {i:03d}" for i in range(MAX_SKILLS)])
		self.assertEqual(index.count("<skill>"), MAX_SKILLS)

	def test_a_global_skill_reaches_an_agent_that_carries_the_tool_but_never_bound_it(self):
		_skill_row("House Style", is_global=1)
		self._carry_the_tool()
		self.assertIn("<name>House Style</name>", self.agent.skill_index())

	def test_without_the_tool_a_global_skill_stays_out_of_the_index(self):
		_skill_row("House Style", is_global=1)
		self.assertEqual(self.agent.skill_index(), "")

	def test_a_disabled_global_skill_stays_out(self):
		_skill_row("House Style", is_global=1, enabled=0)
		self._carry_the_tool()
		self.assertEqual(self.agent.skill_index(), "")

	def test_a_skill_that_is_global_and_bound_appears_once(self):
		_skill_row("House Style", is_global=1)
		index = self._bind("House Style")
		self.assertEqual(index.count("<name>House Style</name>"), 1)

	def test_a_system_generated_agent_still_gets_global_skills(self):
		"""Its skills table is locked, so global is the only way to reach the built-in assistant."""
		_skill_row("House Style", is_global=1)
		self._carry_the_tool()
		self.agent.is_system_generated = 1
		self.agent.save(ignore_permissions=True)
		self.assertIn("<name>House Style</name>", self.agent.skill_index())


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
		self.agent.set("skills", [{"skill": "Expense Approval"}, {"skill": "Model Only"}])
		self.agent.save()
		self.assertEqual(
			[(row["name"], row["command"]) for row in self.agent.invocable_skills()],
			[("Expense Approval", "expense-approval"), ("House Style", "house-style")],
		)

	def test_the_tool_is_not_needed_to_start_a_skill_by_hand(self):
		_skill_row("House Style", is_global=1, user_invocable=1)
		self.assertEqual([row["name"] for row in self.agent.invocable_skills()], ["House Style"])
		self.assertEqual(self.agent.skill_index(), "")


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

	def test_binding_a_skill_attaches_the_tool_automatically(self):
		_skill_row("Expense Approval")
		self.assertIsNone(self._tool())
		self._bind("Expense Approval")
		self.assertIn("load_skill", [row.tool for row in self.agent.tools])

	def test_a_bound_skill_loads_its_instructions(self):
		_skill_row("Expense Approval")
		self._bind("Expense Approval")
		tool = self._tool()
		self.assertEqual(set(tool.parameters["properties"]), {"name"})
		self.assertEqual(tool(name="Expense Approval"), "Body of Expense Approval.")

	def test_a_global_skill_is_loadable_by_an_agent_carrying_the_builtin(self):
		_skill_row("House Style", is_global=1)
		self.agent.append("tools", {"tool": "load_skill"})
		self.agent.save()
		self.assertEqual(self._tool()(name="House Style"), "Body of House Style.")

	def test_another_agents_skill_is_refused_and_the_available_ones_are_named(self):
		_skill_row("Mine")
		_skill_row("Theirs")
		self._bind("Mine")
		self.agent.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "No skill named Theirs. Available: Mine"):
			self._tool()(name="Theirs")

	def test_a_disabled_skill_cannot_be_loaded(self):
		_skill_row("Retired", enabled=0)
		_skill_row("Live")
		self._bind("Retired", "Live")
		with self.assertRaisesRegex(frappe.ValidationError, "No skill named Retired"):
			self._tool()(name="Retired")

	def test_the_builtin_assistant_carries_the_tool_and_loads_a_global_skill(self):
		from flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant

		sync_builtin_assistant(self.model_doc.name)
		assistant = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_TITLE)
		self.assertIn("load_skill", [row.tool for row in assistant.tools])
		_skill_row("House Style", is_global=1)
		self.assertEqual(self._tool(assistant)(name="House Style"), "Body of House Style.")

	def test_the_tool_travels_to_the_server_with_the_agents_schemas(self):
		_skill_row("House Style")
		self._bind("House Style")
		names = [t["function"]["name"] for t in self.agent.client_tool_config()["client_tools"]]
		self.assertIn("load_skill", names)

	def test_an_unbound_tool_refuses(self):
		from flow.tools.builtins import bind_load_skill

		with self.assertRaisesRegex(frappe.ValidationError, "Skills are not configured"):
			bind_load_skill(None)(name="House Style")
