# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow import api
from flow.api import attach_file, submit_feedback
from flow.daemon.client import DaemonClient
from flow.memory import store as memory_store
from flow.permissions import FLOW_USER_ROLE
from flow.tests.fake_daemon import FakeDaemon, pause
from flow.tests.test_live_server import LiveServerCase
from flow.tools.builtins import sync_builtin_tools

OTHER = "api-other-user@example.com"


def _model_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test API Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent_doc(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
		"title": "Test API Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


class TestAttachFile(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _file(self, file_name: str = "report.txt", content: str = "report body"):
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
		).insert()

	def test_attach_file_returns_chip_metadata_and_stages_text(self):
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import staged_attachment

		file_doc = self._file()
		chip = attach_file(file_doc.name)

		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(chip["file_name"], "report.txt")
		self.assertNotIn("extracted_text", chip)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "report body")

	def test_attach_file_strips_and_resolves_input(self):
		file_doc = self._file()
		chip = attach_file(f"  {file_doc.name}  ")
		self.assertEqual(chip["file"], file_doc.name)

	def test_attach_file_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("")

	def test_attach_file_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("   ")

	def test_attach_file_unsupported_type_surfaces_at_upload(self):
		file_doc = self._file(file_name="data.bin", content="x")
		with self.assertRaisesRegex(frappe.ValidationError, "Unsupported file type"):
			attach_file(file_doc.name)


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	frappe.get_doc("User", email).add_roles(FLOW_USER_ROLE)
	return email


class TestSubmitFeedback(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Feedback Test Model")).insert()
		self.agent = frappe.get_doc(
			_agent_doc(self.model.name, title="Feedback Test Agent", tools=[{"tool": "update_memory"}])
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		memory_store.drop_table()

	def _run(self, status: str = "Completed", agent: str | None = None, **fields) -> str:
		session = frappe.get_doc({"doctype": "Flow Session", "agent": agent or self.agent.name}).insert(
			ignore_permissions=True
		)
		return (
			frappe.get_doc(
				{
					"doctype": "Flow Run",
					"session": session.name,
					"source": "Manual",
					"status": status,
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_up_rating_persists(self):
		run = self._run()
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Up")

	def test_denied_run_is_finished(self):
		run = self._run(status="Denied")
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})

	def test_down_with_comment_persists(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Wrong item code.")
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual(doc.feedback_rating, "Down")
		self.assertEqual(doc.feedback_comment, "Wrong item code.")

	def test_rejects_invalid_rating(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rating"):
			submit_feedback(self._run(), "Sideways")

	def test_rejects_unfinished_run(self):
		with self.assertRaisesRegex(frappe.ValidationError, "finished"):
			submit_feedback(self._run(status="Running"), "Up")

	def test_rejects_overlong_comment(self):
		with self.assertRaisesRegex(frappe.ValidationError, "characters"):
			submit_feedback(self._run(), "Down", comment="x" * 501)

	def test_rejects_other_users_run(self):
		run = self._run()
		frappe.set_user(_ensure_user("feedback-other-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			submit_feedback(run, "Up")

	def test_read_only_share_cannot_change_feedback(self):
		run = self._run()
		other = _ensure_user("feedback-read-only@example.com")
		frappe.share.add("Flow Run", run, other, read=1, write=0)
		frappe.set_user(other)
		with self.assertRaises(frappe.PermissionError):
			submit_feedback(run, "Up")

	def test_down_comment_saved_as_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		memory = frappe.get_doc("Flow Agent Memory", result["memory"])
		self.assertEqual(memory.agent, self.agent.name)
		self.assertEqual(memory.scope, "Agent")
		self.assertEqual(memory.source, "Feedback")
		self.assertEqual(memory.source_run, run)
		self.assertEqual(memory.content, "Widget A maps to WGT-001.")

	def test_down_comment_without_memory_tool_records_but_skips_memory(self):
		other = frappe.get_doc(_agent_doc(self.model.name, title="Feedback No Memory Agent")).insert()
		run = self._run(agent=other.name)
		result = submit_feedback(run, "Down", comment="Fix it.")
		self.assertNotIn("memory", result)
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Down")
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": other.name}))

	def test_up_never_saves_memory(self):
		result = submit_feedback(self._run(), "Up", comment="Nice.")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_down_without_comment_saves_no_memory(self):
		result = submit_feedback(self._run(), "Down")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_none_clears_rating(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Not quite.")
		self.assertEqual(submit_feedback(run, "None"), {"rating": None})
		doc = frappe.get_doc("Flow Run", run)
		self.assertFalse(doc.feedback_rating)
		self.assertIsNone(doc.feedback_comment)

	def test_none_keeps_saved_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		submit_feedback(run, "None")
		self.assertTrue(frappe.db.exists("Flow Agent Memory", result["memory"]))


class ApiCase(IntegrationTestCase):
	"""A model, an agent and a scripted flow server behind the endpoints."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model = frappe.get_doc(_model_doc(title="Endpoint Model")).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name, title="Endpoint Agent")).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def create(self, **fields) -> str:
		return api.create_session(self.agent.name, **fields)["name"]

	def run_status(self, run: str) -> str:
		return frappe.db.get_value("Flow Run", run, "status")


class TestSessionEndpoints(ApiCase):
	def test_every_endpoint_is_whitelisted(self):
		for name in api.__all__:
			frappe.is_whitelisted(frappe.get_attr(f"flow.api.{name}"))

	def test_boot_lists_enabled_agents_and_models(self):
		hidden = frappe.get_doc(_agent_doc(self.model.name, title="Hidden Agent", enabled=0)).insert()
		data = api.boot()
		names = [row.name for row in data["agents"]]
		self.assertIn(self.agent.name, names)
		self.assertNotIn(hidden.name, names)
		self.assertIn(self.model.name, [row.name for row in data["models"]])
		self.assertIn("txt", data["file_types"])
		self.assertIn("default_agent", data)

	def test_create_session_names_the_agent_and_keeps_auto_approve(self):
		data = api.create_session(self.agent.name, model=self.model.name, title=" Hello ", auto_approve="1")
		self.assertEqual(
			(data["agent"], data["model"], data["title"], data["source"], data["auto_approve"], data["runs"]),
			(self.agent.name, self.model.name, "Hello", "Manual", True, []),
		)
		self.assertTrue(self.daemon.configs[data["name"]]["auto_approve"])
		self.assertFalse(api.create_session(self.agent.name)["auto_approve"])

	def test_create_session_defaults_to_the_assistant(self):
		from flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant

		sync_builtin_assistant(self.model.name)
		self.assertEqual(api.create_session()["agent"], ASSISTANT_AGENT_TITLE)
		self.assertEqual(api.boot()["default_agent"], ASSISTANT_AGENT_TITLE)

	def test_blank_input_is_refused(self):
		name = self.create()
		with self.assertRaisesRegex(frappe.ValidationError, "Session is required"):
			api.session("  ")
		with self.assertRaisesRegex(frappe.ValidationError, "Message is required"):
			api.run(name, " ")
		with self.assertRaisesRegex(frappe.ValidationError, "Model is required"):
			api.set_model(name, "")
		with self.assertRaisesRegex(frappe.ValidationError, "Title is required"):
			api.set_title(name, "  ")
		with self.assertRaisesRegex(frappe.ValidationError, "Path must be"):
			api.entries(name, path="branch")
		for answers in ("nope", "[1]", 3):
			with self.assertRaisesRegex(frappe.ValidationError, "JSON object"):
				api.resume(name, answers)

	def test_sessions_are_for_their_owner(self):
		name = self.create()
		frappe.set_user(_ensure_user(OTHER))
		for call in (
			lambda: api.session(name),
			lambda: api.run(name, "hi"),
			lambda: api.set_title(name, "x"),
			lambda: api.delete_session(name),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		self.assertEqual(api.list_sessions(), [])

	def test_list_sessions_shows_own_manual_sessions_newest_first(self):
		first = self.create(title="First")
		second = self.create(title="Second")
		trigger = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "source": "Trigger", "title": "Fired"}
		).insert()
		frappe.db.set_value("Flow Session", first, "modified", "2026-01-01 00:00:00", update_modified=False)
		# the test site keeps older committed sessions, so only the newest position is fixed
		frappe.set_user(_ensure_user(OTHER))
		foreign = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "title": "Theirs"}
		).insert()
		frappe.set_user("Administrator")

		rows = api.list_sessions()
		names = [row.name for row in rows]
		self.assertEqual(names[0], second)
		self.assertIn(first, names)
		self.assertNotIn(trigger.name, names)
		self.assertNotIn(foreign.name, names)
		self.assertEqual(set(rows[0].keys()), {"name", "title", "agent", "model", "modified"})
		self.assertEqual([row.name for row in api.list_sessions(limit=1)], [second])

	def test_list_sessions_escapes_like_wildcards_in_the_query(self):
		percent = self.create(title="100% done")
		self.create(title="100 percent done")
		underscore = self.create(title="a_b")
		self.create(title="aXb")
		self.assertEqual([row.name for row in api.list_sessions("100%")], [percent])
		self.assertEqual([row.name for row in api.list_sessions("a_b")], [underscore])
		self.assertEqual(len(api.list_sessions("done")), 2)

	def test_run_answers_started_and_sync_session_completes_the_run(self):
		name = self.create()
		started = api.run(name, "hi")
		self.assertEqual(started["status"], "started")
		self.assertEqual(self.run_status(started["run"]), "Running")
		self.assertEqual(self.daemon.calls[-1], ("run", name, "hi"))

		data = api.sync_session(name)
		self.assertEqual(
			[(run.name, run.status, run.error) for run in data["runs"]], [(started["run"], "Completed", None)]
		)
		self.assertEqual(data["title"], self.daemon.title)
		again = api.sync_session(name)
		self.assertEqual(again, data)
		self.assertEqual(frappe.db.count("Flow Run", {"session": name}), 1)
		self.assertEqual(frappe.db.count("Flow Session Message", {"parent": name}), 4)

	def test_run_answers_steered_with_the_active_run(self):
		self.daemon.answer = lambda seq, run_id, message: []
		name = self.create()
		first = api.run(name, "hi")["run"]
		self.daemon.running = True
		self.assertEqual(api.run(name, "and this"), {"run": first, "status": "steered"})
		self.assertEqual(frappe.db.count("Flow Run", {"session": name}), 1)

	def test_resume_answers_the_paused_run(self):
		self.daemon.answer = pause
		name = self.create()
		run = api.run(name, "delete it")["run"]
		self.assertEqual(api.sync_session(name)["runs"][0]["status"], "Paused")
		self.assertEqual(api.resume(name, '{"c9": "Approve"}'), {"run": run, "status": "started"})
		self.assertEqual(self.daemon.calls[-1], ("resume", name, {"c9": "Approve"}, 4))
		self.assertEqual(self.run_status(run), "Running")
		self.assertEqual(api.sync_session(name)["runs"][0]["status"], "Completed")

	def test_abort_cancel_and_entries_pass_through(self):
		name = self.create()
		self.assertEqual(api.abort(name), {"status": "idle"})
		self.assertEqual(api.cancel_pending(name), {"status": "idle"})
		api.run(name, "hi")
		self.assertEqual(api.entries(name, since="2")["entries"][0]["seq"], 3)
		self.assertEqual(self.daemon.calls[-1], ("entries", name, 2, "active"))

	def test_settings_persist_on_the_session(self):
		name = self.create()
		other = frappe.get_doc(_model_doc(title="Endpoint Other Model")).insert()
		self.assertEqual(api.set_model(name, f" {other.name} "), {"model": other.name})
		self.assertEqual(api.set_title(name, "  Renamed  "), {"title": "Renamed"})
		self.assertEqual(api.set_auto_approve(name, "1"), {"auto_approve": True})
		doc = frappe.get_doc("Flow Session", name)
		self.assertEqual((doc.model, doc.title, doc.auto_approve), (other.name, "Renamed", 1))
		self.assertEqual(api.set_auto_approve(name, 0), {"auto_approve": False})
		self.assertEqual(api.session(name)["auto_approve"], False)
		self.assertEqual(self.daemon.configs[name]["auto_approve"], False)

	def test_trigger_sessions_cannot_disable_auto_approve(self):
		doc = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "source": "Trigger"}
		).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "always auto-approve"):
			api.set_auto_approve(doc.name, 0)
		self.assertEqual(api.set_auto_approve(doc.name, 1), {"auto_approve": True})

	def test_session_syncs_an_open_run_but_not_a_settled_one(self):
		name = self.create()
		run = api.run(name, "hi")["run"]
		self.daemon.calls.clear()
		data = api.session(name)
		self.assertEqual(data["runs"][0]["status"], "Completed")
		self.assertEqual(self.daemon.calls[0], ("get_session", name))
		self.daemon.calls.clear()
		self.assertEqual(api.session(name), data)
		self.assertEqual(self.daemon.calls, [])
		self.assertEqual(self.run_status(run), "Completed")

	def test_delete_session_removes_the_session_and_its_server_copy(self):
		name = self.create()
		with patch("flow.knowledge.attachment_store.delete"):
			self.assertEqual(api.delete_session(name), {"status": "deleted"})
		self.assertFalse(frappe.db.exists("Flow Session", name))
		self.assertIn(("delete_session", name), self.daemon.calls)


class TestLiveEndpoints(LiveServerCase):
	def test_a_run_returns_its_placeholder_and_a_terminal_sync_completes_it(self):
		name = api.create_session(self.agent.name)["name"]
		started = frappe.call("flow.api.run", session=name, message="hello there")
		self.assertEqual(started["status"], "started")
		self.assertEqual(frappe.db.get_value("Flow Run", started["run"], "status"), "Running")

		self.wait_idle(name)
		data = api.sync_session(name)
		self.assertEqual([(run.name, run.status) for run in data["runs"]], [(started["run"], "Completed")])
		self.assertEqual(data["title"], "hello there")
		self.assertEqual(api.entries(name)["entries"][-1]["type"], "run_ended")
		self.assertEqual(
			frappe.db.get_value("Flow Run", started["run"], "output"), "Mock reply to: hello there"
		)
