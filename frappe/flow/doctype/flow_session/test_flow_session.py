# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json
import re
from unittest.mock import call, patch

import frappe
from flow_harness.session.config import SessionConfig
from frappe.tests import IntegrationTestCase

from flow.daemon import lifecycle
from flow.daemon.client import DaemonClient, DaemonError
from flow.flow.doctype.flow_session.flow_session import FlowSession
from flow.flow.doctype.flow_session_attachment.test_flow_session_attachment import png_bytes
from flow.permissions import FLOW_USER_ROLE
from flow.tests.fake_daemon import PENDING, TITLE, FakeDaemon, pause, turn
from flow.tools.builtins import sync_builtin_tools

DELETE = "flow.flow.doctype.flow_session.flow_session._delete_server_session"


def _insert_agent() -> str:
	model = frappe.get_doc(
		{"doctype": "Flow Model", "title": "Purge Test Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
	).insert()
	agent = frappe.get_doc(
		{"doctype": "Flow Agent", "title": "Purge Test Agent", "model": model.name, "instructions": "x"}
	).insert()
	return agent.name


class TestFlowSession(IntegrationTestCase):
	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Session Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Session Test Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_session_can_be_created_without_title(self):
		doc = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		self.assertIsNone(doc.title)

	def test_session_agent_is_locked_after_creation(self):
		other_agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Other Session Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		doc = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		doc.agent = other_agent.name
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change the agent"):
			doc.save(ignore_permissions=True)


class TestClearOldLogs(IntegrationTestCase):
	def setUp(self):
		self.server_delete = self.enterContext(patch(DELETE))
		self.agent = _insert_agent()

	def tearDown(self):
		frappe.db.rollback()

	def _session_with_run(self, *, age_days: int) -> tuple[str, str, str]:
		f = frappe.get_doc({"doctype": "File", "file_name": "f.txt", "content": "x", "is_private": 1}).insert(
			ignore_permissions=True
		)
		session = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent, "title": "chat"})
		session.append("messages", {"role": "user", "content": "hi"})
		session.append("attachments", {"file": f.name, "file_name": "f.txt", "file_size": 1})
		session.insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": session.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		old = frappe.utils.add_days(frappe.utils.now(), -age_days)
		frappe.db.set_value("Flow Session", session.name, "modified", old, update_modified=False)
		return session.name, run.name, f.name

	def test_old_session_and_linked_run_and_messages_are_purged(self):
		old_session, old_run, old_file = self._session_with_run(age_days=100)

		FlowSession.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Flow Session", old_session))
		self.assertFalse(frappe.db.exists("Flow Run", old_run))
		self.assertEqual(frappe.db.count("Flow Session Message", {"parent": old_session}), 0)
		self.assertEqual(frappe.db.count("Flow Session Attachment", {"parent": old_session}), 0)
		self.assertFalse(frappe.db.exists("File", old_file))
		self.server_delete.assert_called_once_with(old_session)

	def test_purge_waits_when_the_flow_server_refuses(self):
		old_session, old_run, _ = self._session_with_run(age_days=100)
		self.server_delete.side_effect = DaemonError(None, "unreachable")

		FlowSession.clear_old_logs(days=30)

		self.assertTrue(frappe.db.exists("Flow Session", old_session))
		self.assertTrue(frappe.db.exists("Flow Run", old_run))

	def test_recent_session_is_kept(self):
		recent_session, recent_run, recent_file = self._session_with_run(age_days=1)

		FlowSession.clear_old_logs(days=30)

		self.assertTrue(frappe.db.exists("Flow Session", recent_session))
		self.assertTrue(frappe.db.exists("Flow Run", recent_run))
		self.assertTrue(frappe.db.exists("File", recent_file))

	def test_purge_keeps_a_file_attached_to_a_business_document(self):
		old_session, _old_run, old_file = self._session_with_run(age_days=100)
		frappe.db.set_value(
			"File",
			old_file,
			{"attached_to_doctype": "User", "attached_to_name": "Administrator"},
			update_modified=False,
		)

		FlowSession.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Flow Session", old_session))
		self.assertTrue(frappe.db.exists("File", old_file))

	def test_purge_keeps_an_orphan_file_used_by_a_recent_session(self):
		old_session, _old_run, old_file = self._session_with_run(age_days=100)
		recent = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent, "title": "recent"})
		recent.append("attachments", {"file": old_file, "file_name": "f.txt", "file_size": 1})
		recent.insert(ignore_permissions=True)

		FlowSession.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Flow Session", old_session))
		self.assertTrue(frappe.db.exists("Flow Session", recent.name))
		self.assertTrue(frappe.db.exists("File", old_file))


class TestAttachmentCleanup(IntegrationTestCase):
	def setUp(self):
		self.server_delete = self.enterContext(patch(DELETE))
		self.agent = _insert_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_on_trash_needs_the_flow_servers_consent(self):
		s = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent}).insert(ignore_permissions=True)
		self.server_delete.side_effect = DaemonError(409, "cannot delete a session with an active run")
		with self.assertRaisesRegex(frappe.ValidationError, "409"):
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Flow Session", s.name))

	def test_on_trash_purges_session_chunks(self):
		s = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent}).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete") as delete:
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		delete.assert_called_once_with(session=s.name)

	def test_cleanup_failure_does_not_block_delete(self):
		s = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent}).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete", side_effect=RuntimeError("store down")):
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Session", s.name))

	def test_on_trash_deletes_linked_runs(self):
		s = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent}).insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": s.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete"):
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Run", run.name))

	def test_clear_old_logs_purges_chunks_for_batch(self):
		s = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent, "title": "old"}).insert(
			ignore_permissions=True
		)
		old = frappe.utils.add_days(frappe.utils.now(), -100)
		frappe.db.set_value("Flow Session", s.name, "modified", old, update_modified=False)
		with patch("flow.knowledge.attachment_store.delete") as delete:
			FlowSession.clear_old_logs(days=30)
		batch = delete.call_args.kwargs["session"]
		self.assertIn(s.name, batch)


class TestFlowSessionOnTheServer(IntegrationTestCase):
	"""The session's verbs, against a scripted flow server."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Server Session Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-model",
				"base_url": "https://llm.example.com/v1",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Server Session Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"tools": [{"tool": "read"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()
		self.session = self.agent.new_session()

	def tearDown(self):
		frappe.db.rollback()

	def runs(self):
		return frappe.db.count("Flow Run", {"session": self.session.name})

	def calls(self, kind):
		return [call for call in self.daemon.calls if call[0] == kind]

	def test_chat_starts_a_turn_and_returns_its_running_placeholder(self):
		self.daemon.title = None
		run = self.session.chat("hello")
		self.assertEqual(
			(run.session, run.input, run.source, run.status, run.output, run.iterations, run.daemon_run_id),
			(self.session.name, "hello", "Manual", "Running", None, 0, None),
		)
		self.assertEqual(self.calls("run"), [("run", self.session.name, "hello")])
		self.assertEqual(self.session.messages, [])
		self.assertEqual((self.session.title, self.session.last_synced_seq), (None, 0))
		self.assertEqual(self.calls("get_session"), [("get_session", self.session.name)])
		self.assertEqual(self.runs(), 1)

	def test_chat_records_where_a_run_came_from(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "trigger probe"}).insert()
		run = self.session.chat("look", source="Trigger", reference_doctype="ToDo", reference_name=todo.name)
		self.assertEqual(
			(run.source, run.reference_doctype, run.reference_name), ("Trigger", "ToDo", todo.name)
		)

	def test_chat_joins_the_active_run_when_a_turn_is_running(self):
		self.daemon.answer = lambda seq, run_id, message: turn(seq, run_id, message)[:2]
		first = self.session.chat("hello")
		self.daemon.running = True
		joined = self.session.chat("and this")
		self.assertEqual(joined.name, first.name)
		self.assertEqual(self.runs(), 1)
		self.assertEqual(self.calls("run")[-1], ("run", self.session.name, "and this"))

	def test_chat_sends_file_text_with_the_turn_and_records_the_attachment(self):
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "notes.txt",
				"content": "the secret code is 1234",
				"is_private": 1,
			}
		).insert()
		run = self.session.chat("summarize this", attachments=[file_doc.name])
		self.assertEqual(
			self.calls("run"),
			[
				(
					"run",
					self.session.name,
					'summarize this\n<file name="notes.txt">\nthe secret code is 1234\n</file>',
				)
			],
		)
		self.assertEqual(run.input, "summarize this")
		self.assertEqual(
			[(a.file, a.file_name, a.run, a.mode, a.extracted_text) for a in self.session.attachments],
			[(file_doc.name, "notes.txt", run.name, "Inline", "the secret code is 1234")],
		)
		self.assertEqual(frappe.db.count("Flow Session Attachment", {"parent": self.session.name}), 1)

	def test_chat_uploads_images_for_a_vision_model(self):
		data = png_bytes()
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "pic.png", "content": data, "is_private": 1}
		).insert()
		run = self.session.chat("what is this", attachments=[file_doc.name])
		self.assertEqual(
			self.daemon.calls[-2:],
			[
				("upload_attachments", self.session.name, [("pic.png", "image/png")]),
				("run", self.session.name, "what is this", ["a0"]),
			],
		)
		self.assertEqual([(a.run, a.mode) for a in self.session.attachments], [(run.name, "Image")])

	def test_chat_drops_its_uploads_when_the_server_refuses_the_turn(self):
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "pic.png", "content": png_bytes(), "is_private": 1}
		).insert()
		self.daemon.paused = True
		with self.assertRaisesRegex(frappe.ValidationError, "paused"):
			self.session.chat("look", attachments=[file_doc.name])
		self.assertEqual(self.daemon.calls[-1], ("cleanup_attachments", self.session.name, ["a0"]))
		self.assertEqual((self.runs(), self.session.attachments), (0, []))

	def test_chat_drops_new_retrieval_chunks_when_the_server_refuses_the_turn(self):
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "large.txt", "content": "A" * 30, "is_private": 1}
		).insert()
		frappe.db.set_value("Flow Model", self.model.name, "context_window", 10)
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		self.daemon.paused = True
		with (
			patch("flow.knowledge.embedder.embed_texts", return_value=[[1.0, 0, 0, 0]]),
			patch("flow.knowledge.attachment_store.ensure_table"),
			patch("flow.knowledge.attachment_store.add"),
			patch("flow.knowledge.attachment_store.delete") as delete,
			patch("flow.knowledge.retriever.retrieve_attachments", return_value=[]),
			self.assertRaisesRegex(frappe.ValidationError, "paused"),
		):
			self.session.chat("look", attachments=[file_doc.name])
		self.assertEqual(
			delete.call_args_list,
			[
				call(session=self.session.name, attachment=file_doc.name),
				call(session=self.session.name, attachment=file_doc.name),
			],
		)

	def test_chat_refuses_a_paused_session(self):
		self.daemon.paused = True
		with self.assertRaisesRegex(frappe.ValidationError, "paused"):
			self.session.chat("more")
		self.assertEqual(self.runs(), 0)

	def test_chat_needs_a_message(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Message is required"):
			self.session.chat("   ")
		self.assertEqual(self.calls("run"), [])

	def test_chat_refuses_an_existing_session_when_its_agent_is_disabled(self):
		self.agent.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.session.chat("hello")
		self.assertEqual(self.calls("run"), [])

	def test_chat_refuses_an_existing_session_when_its_model_is_disabled(self):
		self.model.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.session.chat("hello")
		self.assertEqual(self.calls("run"), [])

	def test_resume_answers_the_batch_the_recorder_names(self):
		self.daemon.answer = pause
		run = self.session.chat("delete it")
		self.session.sync()
		run.reload()
		self.assertEqual((run.status, run.approval_seq, json.loads(run.questions)), ("Paused", 4, [PENDING]))
		self.daemon.paused = True
		resumed = self.session.resume({"c9": "Approve"})
		self.assertEqual(resumed.name, run.name)
		self.assertEqual(
			(resumed.status, resumed.output, resumed.daemon_run_id, resumed.approval_seq),
			("Running", None, "r1", 0),
		)
		self.assertFalse(resumed.questions)
		self.assertEqual(self.calls("resume"), [("resume", self.session.name, {"c9": "Approve"}, 4)])
		self.assertEqual(self.runs(), 1)

	def test_resume_needs_a_paused_run(self):
		with self.assertRaisesRegex(frappe.ValidationError, "no paused run"):
			self.session.resume({"c1": "Approve"})
		self.assertEqual(self.calls("resume"), [])

	def test_cancel_pending_stops_the_paused_run(self):
		self.daemon.answer = pause
		run = self.session.chat("delete it")
		self.session.sync()
		run.reload()
		self.daemon.paused = True
		self.assertEqual(self.session.cancel_pending(), "cancelled")
		run.reload()
		self.assertEqual((run.status, run.error), ("Failed", "Stopped by user."))
		self.assertEqual(self.session.cancel_pending(), "idle")

	def test_abort_reports_the_servers_answer(self):
		self.assertEqual(self.session.abort(), "idle")
		self.daemon.running = True
		self.assertEqual(self.session.abort(), "aborting")

	def test_set_model_sends_the_models_credentials_and_records_the_choice(self):
		other = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Other Model",
				"model_id": "openai/gpt-4o",
				"api_key": "sk-other",
				"base_url": "https://other.example.com",
				"enabled": 1,
			}
		).insert()
		self.session.set_model(other.name)
		self.assertEqual(
			self.calls("set_model"),
			[
				(
					"set_model",
					self.session.name,
					"openai/gpt-4o",
					{"api_key": "sk-other", "api_base": "https://other.example.com"},
				)
			],
		)
		self.assertEqual(frappe.db.get_value("Flow Session", self.session.name, "model"), other.name)
		other.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			self.session.set_model(other.name)
		self.assertEqual(len(self.calls("set_model")), 1)

	def test_set_title_renames_both_sides(self):
		self.session.set_title("Renamed")
		self.assertEqual(
			self.calls("patch_config"), [("patch_config", self.session.name, {"title": "Renamed"})]
		)
		self.assertEqual(frappe.db.get_value("Flow Session", self.session.name, "title"), "Renamed")

	def test_set_auto_approve_changes_the_servers_policy(self):
		self.assertFalse(self.daemon.configs[self.session.name]["auto_approve"])
		self.assertFalse(self.session.auto_approve)
		self.session.set_auto_approve(True)
		self.assertEqual(
			self.calls("patch_config"), [("patch_config", self.session.name, {"auto_approve": True})]
		)
		self.assertTrue(self.daemon.configs[self.session.name]["auto_approve"])
		self.assertTrue(frappe.db.get_value("Flow Session", self.session.name, "auto_approve"))

	def test_entries_proxies_the_server(self):
		self.daemon.rows = turn(1, "r1")
		self.assertEqual(self.session.entries(since=6, path="all"), {"entries": turn(1, "r1")[6:]})
		self.assertEqual(self.calls("entries"), [("entries", self.session.name, 6, "all")])

	def test_a_server_refusal_is_a_validation_error(self):
		with patch.object(self.daemon, "run", side_effect=DaemonError(400, "attachment 'x' not found")):
			with self.assertRaisesRegex(frappe.ValidationError, "400.*not found"):
				self.session.chat("hello")
		with patch.object(self.daemon, "run", side_effect=DaemonError(None, "ConnectError")):
			with self.assertRaisesRegex(frappe.ValidationError, "unreachable"):
				self.session.chat("hello")
		self.assertEqual(self.runs(), 0)

	def test_a_session_without_a_server_twin_is_read_only_history(self):
		with patch.object(self.daemon, "run", side_effect=DaemonError(404, "session not found")):
			with self.assertRaisesRegex(frappe.ValidationError, "read-only history"):
				self.session.chat("hello")
		self.assertEqual(self.runs(), 0)

	def test_deleting_a_session_drops_the_server_copy_first(self):
		self.daemon.running = True
		with patch("flow.knowledge.attachment_store.delete"):
			with self.assertRaisesRegex(frappe.ValidationError, "409"):
				self.session.delete()
			self.assertTrue(frappe.db.exists("Flow Session", self.session.name))
			self.daemon.running = False
			self.daemon.missing = True
			self.session.delete()
		self.assertFalse(frappe.db.exists("Flow Session", self.session.name))


class TestFlowSessionServerConfig(IntegrationTestCase):
	"""The flow server session a Flow Session describes."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Config Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-model",
				"base_url": "https://llm.example.com/v1",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Config Agent",
				"model": self.model.name,
				"instructions": "Be terse.",
				"max_iterations": 7,
				"tools": [{"tool": "read"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def session(self, **fields):
		doc = {"doctype": "Flow Session", "agent": self.agent.name, "title": "Hello", **fields}
		return frappe.get_doc(doc).insert()

	def config(self, **fields):
		return self.session(**fields).server_config()

	def test_the_config_is_valid_for_the_server(self):
		session = self.session()
		config = session.server_config()
		SessionConfig.model_validate(config)
		self.assertEqual(config["session_id"], session.name)
		self.assertRegex(session.name, re.compile(r"^[A-Za-z0-9_-]{1,64}$"))
		self.assertEqual(config["title"], "Hello")
		self.assertEqual(config["model"], "openai/gpt-4o-mini")
		self.assertEqual(config["api_key"], "sk-model")
		self.assertEqual(config["api_base"], "https://llm.example.com/v1")
		self.assertEqual(config["system_prompt"], "Be terse.")
		self.assertEqual(config["max_turns"], 7)
		self.assertEqual(config["callback_token"], "site-token")
		self.assertEqual(
			config["callback_url"], f"{lifecycle.site_url()}/api/method/flow.daemon.callback.callback"
		)
		self.assertTrue(config["notify_run_ended"])
		self.assertEqual(config["cwd"], str(lifecycle.session_root()))
		self.assertEqual(
			config["user_context"],
			{
				"site": frappe.local.site,
				"user": "Administrator",
				"agent": self.agent.name,
				"session": session.name,
			},
		)
		self.assertNotIn("callback_timeout", config)

	def test_sessions_get_no_server_tools_or_skills_only_the_agents_schemas(self):
		config = self.config()
		self.assertEqual(config["tools"], [])
		self.assertEqual(config["extension_tools"], [])
		self.assertFalse(config["skills_enabled"])
		self.assertEqual([tool["function"]["name"] for tool in config["client_tools"]], ["read", "execute"])
		self.assertEqual(config["confirm_tools"], ["execute"])
		self.assertFalse(config["auto_approve"])
		self.assertTrue(config["auto_compact"])

	def test_an_empty_prompt_is_still_verbatim(self):
		frappe.db.set_value("Flow Agent", self.agent.name, "instructions", "")
		self.assertEqual(self.config()["system_prompt"], "")

	def test_the_sessions_model_overrides_the_agents_and_takes_provider_credentials(self):
		bare = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Bare Model", "model_id": "openai/gpt-4o", "enabled": 1}
		).insert()
		provider = {"api_key": "sk-provider", "base_url": "https://provider.example.com"}
		with patch("flow.lib.model.resolve_provider_credentials", return_value=provider):
			config = self.config(model=bare.name)
			own = self.config()
		self.assertEqual(
			(config["model"], config["api_key"], config["api_base"]), ("openai/gpt-4o", *provider.values())
		)
		self.assertEqual((own["api_key"], own["api_base"]), ("sk-model", "https://llm.example.com/v1"))

	def test_without_a_title_the_server_titles_the_session(self):
		config = self.config(title=None)
		SessionConfig.model_validate(config)
		self.assertIsNone(config["title"])

	def test_default_iterations_apply_when_unset(self):
		self.agent.db_set("max_iterations", 0)
		self.assertEqual(self.config()["max_turns"], 20)

	def test_trigger_sessions_always_auto_approve(self):
		session = self.session(source="Trigger", auto_approve=0)
		self.assertTrue(session.auto_approve)
		self.assertTrue(session.server_config()["auto_approve"])
		with self.assertRaisesRegex(frappe.ValidationError, "always auto-approve"):
			session.set_auto_approve(False)

	def test_callback_timeout_comes_from_site_config(self):
		with patch.dict(frappe.local.conf, {"flow_callback_timeout": 30}):
			self.assertEqual(self.config()["callback_timeout"], 30)

	def test_disabled_model_or_agent_is_refused(self):
		session = self.session()
		self.model.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			session.server_config()
		self.model.db_set("enabled", 1)
		self.agent.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			session.server_config()

	def test_the_user_must_be_allowed_to_read_the_model(self):
		session = self.session()
		with patch.object(frappe, "has_permission", side_effect=frappe.PermissionError) as check:
			with self.assertRaises(frappe.PermissionError):
				session.server_config()
		check.assert_called_once_with("Flow Model", "read", self.model.name, throw=True)


class TestFlowSessionModelPermission(IntegrationTestCase):
	"""A session runs only on a model its user may read."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.allowed = self.model("Allowed Model")
		self.restricted = self.model("Restricted Model")
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Permission Agent",
				"model": self.restricted.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		self.user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "model-perm@example.com",
				"first_name": "Model Perm",
				"send_welcome_email": 0,
				"roles": [{"role": FLOW_USER_ROLE}],
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def model(self, title):
		return frappe.get_doc(
			{"doctype": "Flow Model", "title": title, "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()

	def session(self, **fields):
		doc = {"doctype": "Flow Session", "agent": self.agent.name, **fields}
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	def restrict_to(self, model_name):
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": self.user.name,
				"allow": "Flow Model",
				"for_value": model_name,
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=self.user.name)

	def restrict_agents_to(self, agent_name):
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": self.user.name,
				"allow": "Flow Agent",
				"for_value": agent_name,
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=self.user.name)

	def test_a_user_kept_from_the_agents_model_is_blocked(self):
		session = self.session()
		self.restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)
		with self.assertRaises(frappe.PermissionError):
			session.server_config()

	def test_a_user_allowed_the_agents_model_may_start(self):
		session = self.session()
		self.restrict_to(self.restricted.name)
		frappe.set_user(self.user.name)
		self.assertEqual(session.server_config()["model"], "openai/gpt-4o-mini")

	def test_the_sessions_model_override_is_checked_the_same_way(self):
		permitted = self.session(model=self.allowed.name)
		kept_out = self.session(model=self.restricted.name)
		self.restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)
		self.assertEqual(permitted.server_config()["model"], "openai/gpt-4o-mini")
		with self.assertRaises(frappe.PermissionError):
			kept_out.server_config()

	def test_a_users_permitted_model_becomes_their_sessions_default(self):
		# Frappe fills a Link from the user's User Permission, so their own sessions
		# run on the model they may use even when the agent's model is off limits.
		self.restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)
		session = self.session()
		self.assertEqual(session.model, self.allowed.name)
		self.assertEqual(session.server_config()["model"], "openai/gpt-4o-mini")

	def test_chat_rechecks_model_permission_for_an_existing_session(self):
		session = self.session(model=self.restricted.name)
		session.db_set("owner", self.user.name)
		self.restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)
		with self.assertRaises(frappe.PermissionError):
			session.chat("hello")

	def test_chat_rechecks_agent_permission_for_an_existing_session(self):
		allowed = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Allowed Permission Agent",
				"model": self.allowed.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		session = self.session(model=self.allowed.name)
		session.db_set("owner", self.user.name)
		self.restrict_agents_to(allowed.name)
		frappe.set_user(self.user.name)
		with self.assertRaises(frappe.PermissionError):
			session.chat("hello")

	def test_resume_rechecks_model_permission(self):
		session = self.session(model=self.restricted.name)
		session.db_set("owner", self.user.name)
		self.daemon.rows = pause(1, "r1")
		self.daemon.paused = True
		session.sync()
		self.restrict_to(self.allowed.name)
		frappe.set_user(self.user.name)
		with self.assertRaises(frappe.PermissionError):
			session.resume({"c9": "approve"})
