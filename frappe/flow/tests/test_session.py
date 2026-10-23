# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.flow.daemon.client import DaemonClient, DaemonError
from frappe.flow.doctype.flow_session_attachment.test_flow_session_attachment import png_bytes
from frappe.flow.lib.session import load_session, new_session
from frappe.flow.permissions import FLOW_USER_ROLE
from frappe.flow.tests.test_fake_daemon import FakeDaemon
from frappe.flow.tests.test_live_server import LiveServerCase
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase

OTHER = "session-other@example.com"


def _ensure_other() -> None:
	if not frappe.db.exists("User", OTHER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": OTHER,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": FLOW_USER_ROLE}],
			}
		).insert(ignore_permissions=True)


class ServerCase(IntegrationTestCase):
	"""A model, an agent and a scripted flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
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
				"tools": [{"tool": "read_records"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestNewSession(ServerCase):
	def test_new_session_starts_its_server_twin(self):
		session = new_session(self.agent, source="Trigger")
		self.assertEqual((session.title, session.source, session.auto_approve), (None, "Trigger", 1))
		# an untitled session is left for the server to title
		self.assertIsNone(self.daemon.configs[session.name]["title"])
		self.assertTrue(self.daemon.configs[session.name]["auto_approve"])
		# outside tests the twin's row is committed before returning, for the server's callbacks
		with (
			patch.dict(frappe.flags, {"in_test": False}),
			patch.object(frappe.db, "commit") as commit,
		):
			new_session(self.agent.name)
		commit.assert_called_once_with()
		with (
			patch.object(
				self.daemon, "create_session", side_effect=DaemonError(400, "host 'x' is not allowed")
			),
			self.assertRaisesRegex(frappe.ValidationError, "400.*not allowed"),
		):
			new_session(self.agent.name)

	def test_new_session_defaults_to_the_assistant_under_the_same_read_checks(self):
		from frappe.flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant

		sync_builtin_assistant(self.model.name)
		session = new_session()
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)
		self.assertIn(session.name, self.daemon.configs)
		_ensure_other()
		frappe.get_doc(
			{"doctype": "User Permission", "user": OTHER, "allow": "Flow Agent", "for_value": self.agent.name}
		).insert()
		# the agent's model is for System Managers only: others are refused, by name, until they pick another
		self.model.append("roles", {"role": "System Manager"})
		self.model.save()
		open_model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Session Open Model",
				"model_id": "openai/gpt-4o",
				"enabled": 1,
			}
		).insert()
		frappe.set_user(OTHER)
		with self.assertRaisesRegex(frappe.PermissionError, self.model.name):
			new_session(self.agent.name)
		self.assertEqual(new_session(self.agent.name, model=open_model.name).model, open_model.name)
		with self.assertRaises(frappe.PermissionError):
			new_session()


class TestLoadSession(ServerCase):
	def test_load_session_continues_the_owners_session_on_its_agent(self):
		_ensure_other()
		session = new_session(self.agent.name)
		other_agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Another Lib Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		other_model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Switched Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		self.assertEqual(load_session(session.name, agent=self.agent.name).agent, self.agent.name)
		with self.assertRaisesRegex(frappe.ValidationError, "bound to agent"):
			load_session(session.name, agent=other_agent.name)

		self.assertEqual(load_session(session.name, model=other_model.name).model, other_model.name)
		load_session(session.name, model=other_model.name)  # already on it: no second switch
		self.assertEqual(
			[call for call in self.daemon.calls if call[0] == "set_model"],
			[
				(
					"set_model",
					session.name,
					"openai/gpt-4o",
					{"api_key": None, "api_base": None, "model_params": None, "reasoning_effort": None},
				)
			],
		)

		frappe.set_user(OTHER)
		with self.assertRaises(frappe.PermissionError):
			load_session(session.name)


class TestSkillCommands(ServerCase):
	"""A /skill:<command> in a message reaches the server as that skill's instructions."""

	def setUp(self):
		super().setUp()
		self._skill("Expense Approval", user_invocable=1)
		self._skill("Model Only")
		self.agent.set("skills", [{"skill": "Expense Approval"}, {"skill": "Model Only"}])
		self.agent.save()
		self.session = new_session(self.agent.name)

	def _skill(self, title: str, **fields) -> None:
		frappe.get_doc(
			{
				"doctype": "Flow Skill",
				"title": title,
				"description": f"When to use {title}.",
				"instructions": "Check the receipt.\n",
				**fields,
			}
		).insert()

	def _sent(self) -> str:
		return [call[2] for call in self.daemon.calls if call[0] == "run"][-1]

	def test_a_command_is_expanded_for_the_server_where_it_was_typed(self):
		run = self.session.chat("/skill:expense-approval  claim 42 ")
		self.assertEqual(
			self._sent(),
			'<skill name="expense-approval" location="Flow Skill/Expense Approval">\n'
			"This is the full skill, already loaded. Follow it; call load_skill only to read a file or folder it mentions.\n\n"
			"Check the receipt.\n</skill>\n\nclaim 42",
		)
		self.assertEqual(run.input, "/skill:expense-approval  claim 42 ")
		# a bare command sends the instructions alone
		self.session.chat("/skill:expense-approval")
		self.assertTrue(self._sent().endswith("Check the receipt.\n</skill>"))
		# a leading command named again stays in the text
		self.session.chat("/skill:expense-approval do /skill:expense-approval")
		sent = self._sent()
		self.assertEqual(sent.count("<skill "), 1)
		self.assertTrue(sent.endswith("</skill>\n\n/skill:expense-approval do /skill:expense-approval"))
		# commands later in the message stay where they were typed
		self._skill("Receipt Check", user_invocable=1, instructions="Match the amounts.")
		self.agent.append("skills", {"skill": "Receipt Check"})
		self.agent.save()
		text = "check /skill:receipt-check then /skill:expense-approval for /skill:receipt-check"
		run = self.session.chat(text)
		sent = self._sent()
		self.assertTrue(sent.startswith('<skill name="receipt-check" location="Flow Skill/Receipt Check">'))
		self.assertIn('Match the amounts.\n</skill>\n\n<skill name="expense-approval"', sent)
		self.assertTrue(sent.endswith(f"Check the receipt.\n</skill>\n\n{text}"))
		self.assertEqual(run.input, text)

	def test_a_skill_not_flagged_for_users_is_refused_before_anything_is_sent(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "No skill named model-only. Available: expense-approval"
		):
			self.session.chat("/skill:model-only")
		self.assertEqual([call for call in self.daemon.calls if call[0] == "run"], [])

	def test_other_text_passes_untouched(self):
		for text in (
			"skill:expense-approval is not a command",
			"what does this do?\n\n> Type /skill:expense-approval to start it.",
			"why can't I use /skill:model-only here?",
		):
			with self.subTest(text):
				self.session.chat(text)
				self.assertEqual(self._sent(), text)


class TestLiveSession(LiveServerCase):
	"""A conversation through a real flow server with the mock model."""

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
		with patch("frappe.flow.knowledge.attachment_store.delete"):
			session.delete()
		with self.assertRaises(DaemonError) as caught:
			self.client.get_session(session.name)
		self.assertEqual(caught.exception.status, 404)

	def test_attachments_reach_the_server(self):
		"""A text file rides inside the message; an image is read by OCR for a text-only
		model and uploaded for one that sees images (the mock model then gets a placeholder)."""
		session = self.agent.new_session()
		note = frappe.get_doc(
			{"doctype": "File", "file_name": "note.txt", "content": "the code is 4711", "is_private": 1}
		).insert()
		run = session.chat("what is the code?", attachments=[note.name])
		self.settle(session, run)
		self.assertEqual(run.status, "Completed")
		self.assertIn("the code is 4711", run.output)  # the mock model echoes the text it was given
		self.assertEqual(
			[(a.file, a.mode, a.run) for a in session.attachments], [(note.name, "Inline", run.name)]
		)

		picture = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "invoice.png",
				"content": png_bytes("INVOICE 4711"),
				"is_private": 1,
			}
		).insert()
		with patch("flow_harness.model.catalog.model_supports_images", return_value=False):
			run = session.chat("read the picture", attachments=[picture.name])
		self.settle(session, run)
		self.assertIn("INVOICE 4711", run.output)
		self.assertEqual(session.attachments[-1].mode, "Inline")

		run = session.chat("and as an image", attachments=[picture.name])  # gpt-4o-mini sees images
		self.settle(session, run)
		self.assertEqual((run.status, session.attachments[-1].mode), ("Completed", "Image"))
		message = [
			e for e in self.client.entries(session.name, path="all")["entries"] if e["type"] == "user_message"
		][-1]
		self.assertEqual(
			[(b["type"], b.get("kind")) for b in message["content"]],
			[("text", None), ("attachment", "image")],
		)
		with patch("frappe.flow.knowledge.attachment_store.delete"):
			session.delete()
