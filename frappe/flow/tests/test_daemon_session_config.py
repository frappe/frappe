# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re
from unittest.mock import patch

import frappe
from flow_harness.session.config import SessionConfig
from frappe.tests import IntegrationTestCase

from flow.daemon import lifecycle, session_config
from flow.tools.builtins import sync_builtin_tools


class TestSessionConfig(IntegrationTestCase):
	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch.object(session_config, "resolve_provider_credentials", return_value={}))
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Payload Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-model",
				"base_url": "https://llm.example.com/v1",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Payload Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"max_iterations": 7,
				"tools": [{"tool": "read"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def config(self, **overrides) -> dict:
		options = {"session_id": "abc123def4", "title": "Hello"} | overrides
		return session_config.build(self.agent, **options)

	def test_the_config_is_valid_for_the_daemon(self):
		config = self.config()
		SessionConfig.model_validate(config)
		self.assertEqual(config["session_id"], "abc123def4")
		self.assertEqual(config["title"], "Hello")
		self.assertEqual(config["model"], "openai/gpt-4o-mini")
		self.assertEqual(config["api_key"], "sk-model")
		self.assertEqual(config["api_base"], "https://llm.example.com/v1")
		self.assertEqual(config["system_prompt"], "Be terse.")
		self.assertEqual(config["max_turns"], 7)
		self.assertEqual(config["callback_token"], "site-token")
		self.assertEqual(
			config["callback_url"], f"{lifecycle.site_url()}/api/method/flow.daemon.callback.tool_callback"
		)
		self.assertEqual(config["cwd"], str(lifecycle.session_root()))
		self.assertEqual(
			config["user_context"],
			{
				"site": frappe.local.site,
				"user": "Administrator",
				"agent": "Payload Agent",
				"session": "abc123def4",
			},
		)
		self.assertNotIn("callback_timeout", config)

	def test_sessions_get_no_daemon_tools_or_skills_only_the_agents_schemas(self):
		config = self.config()
		self.assertEqual(config["tools"], [])
		self.assertEqual(config["extension_tools"], [])
		self.assertFalse(config["skills_enabled"])
		self.assertEqual([tool["function"]["name"] for tool in config["client_tools"]], ["read", "execute"])
		self.assertEqual(config["client_tools"][0]["type"], "function")
		self.assertIn("properties", config["client_tools"][0]["function"]["parameters"])
		self.assertEqual(config["confirm_tools"], ["execute"])
		self.assertFalse(config["auto_approve"])
		self.assertTrue(config["auto_compact"])

	def test_an_empty_prompt_is_still_verbatim(self):
		self.agent.instructions = ""
		self.assertEqual(self.config()["system_prompt"], "")

	def test_provider_credentials_fill_in_for_a_model_without_its_own(self):
		bare = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Bare Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		provider = {"api_key": "sk-provider", "base_url": "https://provider.example.com"}
		with patch.object(session_config, "resolve_provider_credentials", return_value=provider):
			config = self.config(model=bare.name)
			own = self.config()
		self.assertEqual(
			(config["model"], config["api_key"], config["api_base"]), ("openai/gpt-4o", *provider.values())
		)
		self.assertEqual((own["api_key"], own["api_base"]), ("sk-model", "https://llm.example.com/v1"))

	def test_without_a_title_the_daemon_titles_the_session(self):
		config = session_config.build(self.agent, session_id="untitled01")
		SessionConfig.model_validate(config)
		self.assertIsNone(config["title"])

	def test_triggers_may_auto_approve(self):
		self.assertTrue(self.config(auto_approve=True)["auto_approve"])

	def test_callback_timeout_comes_from_site_config(self):
		with patch.dict(frappe.local.conf, {"flow_callback_timeout": 30}):
			self.assertEqual(self.config()["callback_timeout"], 30)

	def test_disabled_model_or_agent_is_refused(self):
		self.model.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.config()
		self.model.db_set("enabled", 1)
		self.agent.enabled = 0
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.config()

	def test_the_user_must_be_allowed_to_read_the_model(self):
		with patch.object(frappe, "has_permission", side_effect=frappe.PermissionError) as check:
			with self.assertRaises(frappe.PermissionError):
				self.config()
		check.assert_called_once_with("Flow Model", "read", self.model.name, throw=True)

	def test_flow_session_names_satisfy_the_daemons_session_id_rule(self):
		session = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert()
		self.assertRegex(session.name, re.compile(r"^[A-Za-z0-9_-]{1,64}$"))
		SessionConfig.model_validate(self.config(session_id=session.name))
