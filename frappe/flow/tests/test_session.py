# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.daemon import lifecycle
from flow.daemon.client import DaemonClient, DaemonError
from flow.flow.doctype.flow_session.flow_session import FlowSession
from flow.lib.agent import Agent
from flow.lib.model import Model
from flow.lib.session import load_session, new_session
from flow.tests.fake_daemon import FakeDaemon
from flow.tools.builtins import sync_builtin_tools

OTHER = "session-other@example.com"
TOKEN = "site-token-live"


class ServerCase(IntegrationTestCase):
	"""A model, an agent and a scripted flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Session Lib Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Session Lib Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"tools": [{"tool": "read"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestNewSession(ServerCase):
	def test_new_session_inserts_the_session_and_its_server_twin(self):
		session = new_session(self.agent.name, model=self.model.name, title="Hello", auto_approve=True)
		self.assertEqual(
			(session.agent, session.model, session.title, session.source, session.auto_approve, session.owner),
			(self.agent.name, self.model.name, "Hello", "Manual", 1, "Administrator"),
		)
		config = self.daemon.configs[session.name]
		self.assertEqual(
			(config["session_id"], config["title"], config["model"], config["auto_approve"]),
			(session.name, "Hello", "openai/gpt-4o-mini", True),
		)
		self.assertEqual([tool["function"]["name"] for tool in config["client_tools"]], ["read", "execute"])

	def test_new_session_commits_the_twin_before_returning_outside_tests(self):
		with (
			patch.dict(frappe.flags, {"in_test": False}),
			patch.object(frappe.db, "commit") as commit,
		):
			new_session(self.agent.name)

		commit.assert_called_once_with()

	def test_an_untitled_session_is_left_for_the_server_to_title(self):
		session = new_session(self.agent, source="Trigger")
		self.assertEqual((session.title, session.source, session.auto_approve), (None, "Trigger", 1))
		self.assertIsNone(self.daemon.configs[session.name]["title"])
		self.assertTrue(self.daemon.configs[session.name]["auto_approve"])

	def test_new_session_defaults_to_the_assistant(self):
		from flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant

		sync_builtin_assistant(self.model.name)
		session = new_session()
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)
		self.assertIn(session.name, self.daemon.configs)

	def test_code_agents_are_not_on_the_server_yet(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Code agents"):
			new_session(Agent(model=Model(model_id="openai/gpt-4o-mini")))
		self.assertEqual(self.daemon.calls, [])

	def test_a_server_refusal_is_a_validation_error(self):
		with patch.object(
			self.daemon, "create_session", side_effect=DaemonError(400, "host 'x' is not allowed")
		):
			with self.assertRaisesRegex(frappe.ValidationError, "400.*not allowed"):
				new_session(self.agent.name)


class TestLoadSession(ServerCase):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("User", OTHER):
			frappe.get_doc(
				{"doctype": "User", "email": OTHER, "first_name": "Other", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		self.session = new_session(self.agent.name)

	def test_load_session_is_for_the_owner(self):
		self.assertEqual(load_session(self.session.name).name, self.session.name)
		frappe.set_user(OTHER)
		with self.assertRaises(frappe.PermissionError):
			load_session(self.session.name)

	def test_load_session_keeps_the_sessions_agent(self):
		other = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Another Lib Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		self.assertEqual(load_session(self.session.name, agent=self.agent.name).agent, self.agent.name)
		with self.assertRaisesRegex(frappe.ValidationError, "bound to agent"):
			load_session(self.session.name, agent=other.name)

	def test_load_session_switches_the_model(self):
		other = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Switched Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		switched = load_session(self.session.name, model=other.name)
		self.assertEqual(switched.model, other.name)
		self.assertEqual(
			[call for call in self.daemon.calls if call[0] == "set_model"],
			[("set_model", self.session.name, "openai/gpt-4o", {"api_key": None, "api_base": None})],
		)
		load_session(self.session.name, model=other.name)
		self.assertEqual(len([call for call in self.daemon.calls if call[0] == "set_model"]), 1)


class TestLiveSession(IntegrationTestCase):
	"""A conversation through a real flow server with the mock model."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not lifecycle._flow_bin().exists():
			raise unittest.SkipTest("the flow server is not installed in this environment")
		tmp = TemporaryDirectory()
		cls.addClassCleanup(tmp.cleanup)
		root = Path(tmp.name)
		cls.enterClassContext(patch.object(lifecycle, "state_dir", return_value=root / "state"))
		cls.enterClassContext(patch.object(lifecycle, "runtime_dir", return_value=root))
		cls.enterClassContext(patch.object(lifecycle, "log_path", return_value=root / "flow-server.log"))
		cls.enterClassContext(patch.object(lifecycle, "_redis_url", return_value=None))
		cls.enterClassContext(patch.dict(frappe.local.conf, {"flow_server_secret": TOKEN}))
		lifecycle.provision_site()
		lifecycle.start()
		cls.addClassCleanup(lifecycle.stop)

	def setUp(self):
		sync_builtin_tools()
		self.client = DaemonClient.for_site()
		self.addCleanup(self.client.close)
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Live Session Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-live",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Live Session Agent",
				"model": self.model.name,
				"instructions": "Reply briefly.",
				"tools": [{"tool": "read"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()
		original = FlowSession.server_config
		# the server's keyless mock model answers every message with an echo
		self.enterContext(
			patch.object(
				FlowSession, "server_config", lambda doc, **kw: {**original(doc, **kw), "model": "mock"}
			)
		)
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))

	def tearDown(self):
		frappe.db.rollback()

	def settle(self, session, run):
		for _ in range(100):
			if not self.client.get_session(session.name)["running"]:
				break
			time.sleep(0.01)
		else:
			self.fail("daemon run did not finish")
		session.sync()
		session.reload()
		run.reload()

	def test_a_conversation_round_trips_through_the_server_into_flow(self):
		session = self.agent.new_session()
		self.assertEqual(self.client.get_session(session.name)["config"]["model"], "mock")
		run = session.chat("hello there")
		self.assertEqual((run.status, run.output), ("Running", None))
		self.settle(session, run)
		self.assertEqual(
			(run.status, run.output, run.iterations, run.error),
			("Completed", "Mock reply to: hello there", 1, None),
		)
		self.assertTrue(run.daemon_run_id)
		self.assertGreater(json.loads(run.usage)["input_tokens"], 0)
		self.assertEqual(
			[(m.role, m.content, m.run) for m in session.messages],
			[("user", "hello there", run.name), ("assistant", "Mock reply to: hello there", run.name)],
		)
		self.assertEqual(session.title, "hello there")
		session.sync()
		self.assertEqual(len(session.messages), 2)

		session.set_auto_approve(True)
		second = self.agent.run("and again", session=session.name)
		self.assertEqual((second.status, second.input), ("Running", "and again"))
		self.settle(session, second)
		self.assertEqual(
			(second.session, second.status, second.input), (session.name, "Completed", "and again")
		)
		self.assertEqual(frappe.db.count("Flow Run", {"session": session.name}), 2)
		self.assertTrue(self.client.get_session(session.name)["config"]["auto_approve"])
		session.set_title("Renamed")
		self.assertEqual(self.client.get_session(session.name)["title"], "Renamed")
		self.assertEqual((session.abort(), session.cancel_pending()), ("idle", "idle"))
		with patch("flow.knowledge.attachment_store.delete"):
			session.delete()
		with self.assertRaises(DaemonError) as caught:
			self.client.get_session(session.name)
		self.assertEqual(caught.exception.status, 404)
