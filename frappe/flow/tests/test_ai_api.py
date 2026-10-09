# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow import api
from flow.api import attach_file, cleanup_attachments, submit_feedback
from flow.daemon.client import DaemonClient
from flow.flow.doctype.flow_session.flow_session import FlowSession
from flow.flow.doctype.flow_session_attachment.test_flow_session_attachment import png_bytes
from flow.lib.session import new_session
from flow.memory import store as memory_store
from flow.permissions import FLOW_USER_ROLE
from flow.tests.test_fake_daemon import FakeDaemon, child_pause, pause
from flow.tests.test_live_server import LiveServerCase
from flow.tools.builtins import sync_builtin_tools

OTHER = "api-other-user@example.com"
MANAGER = "api-manager@example.com"


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

	def test_attach_file_prepares_image_ocr_without_forcing_text_delivery(self):
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import staged_attachment

		file_doc = self._file(file_name="pic.png", content=png_bytes())
		with patch(
			"flow.flow.doctype.flow_session_attachment.flow_session_attachment.extract_file",
			return_value="OCR",
		):
			self.assertEqual(attach_file(file_doc.name)["file_name"], "pic.png")
		data = staged_attachment(file_doc.name)
		self.assertIsNone(data["extracted_text"])
		self.assertEqual(data["ocr_text"], "OCR")

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


def _ensure_manager() -> str:
	"""A System Manager without the Flow User role."""
	user = frappe.get_doc("User", _ensure_user(MANAGER))
	user.add_roles("System Manager")
	user.remove_roles(FLOW_USER_ROLE)
	return user.name


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

	def test_withdrawing_a_thumbs_down_forgets_its_memory(self):
		run = self._run()
		memory = submit_feedback(run, "Down", comment="Wrong item code.")["memory"]
		self.assertEqual(submit_feedback(run, "None"), {"rating": None, "forgotten": 1})
		self.assertFalse(frappe.db.exists("Flow Agent Memory", memory))

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
		submit_feedback(run, "Up")
		self.assertEqual(submit_feedback(run, "None"), {"rating": None})
		doc = frappe.get_doc("Flow Run", run)
		self.assertFalse(doc.feedback_rating)
		self.assertIsNone(doc.feedback_comment)


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
		model = next(row for row in data["models"] if row.name == self.model.name)
		self.assertEqual(model.model_id, "openai/gpt-4o-mini")
		self.assertIn("context_window", model)
		self.assertIn("txt", data["file_types"])
		self.assertIn("default_agent", data)

	def test_boot_names_the_user_and_their_settings_rights(self):
		data = api.boot()
		self.assertEqual(data["user"]["name"], "Administrator")
		self.assertIn("full_name", data["user"])
		self.assertEqual(data["permissions"]["Flow Provider"], ["read", "write", "create", "delete"])
		frappe.set_user(_ensure_user(OTHER))
		data = api.boot()
		self.assertEqual(data["user"]["name"], OTHER)
		self.assertEqual(data["permissions"]["Flow Provider"], [])
		self.assertEqual(data["permissions"]["Flow Model"], ["read"])

	def test_create_session_names_the_agent_and_keeps_auto_approve(self):
		data = api.create_session(self.agent.name, model=self.model.name, title=" Hello ", auto_approve="1")
		self.assertEqual(
			(data["agent"], data["model"], data["title"], data["source"], data["auto_approve"], data["runs"]),
			(self.agent.name, self.model.name, "Hello", "Manual", True, []),
		)
		self.assertTrue(self.daemon.configs[data["name"]]["auto_approve"])
		plain = api.create_session(self.agent.name)
		self.assertFalse(plain["auto_approve"])
		self.assertEqual(plain["model"], self.model.name)  # the agent's model, with no override
		self.assertIsNone(frappe.db.get_value("Flow Session", plain["name"], "model"))

	def test_cleanup_only_deletes_files_the_run_did_not_claim(self):
		name = self.create()
		unused = frappe.get_doc(
			{"doctype": "File", "file_name": "unused.txt", "content": "unused", "is_private": 1}
		).insert()
		claimed = frappe.get_doc(
			{"doctype": "File", "file_name": "claimed.txt", "content": "claimed", "is_private": 1}
		).insert()
		doc = frappe.get_doc("Flow Session", name)
		doc.append(
			"attachments",
			{"file": claimed.name, "file_name": claimed.file_name, "file_size": claimed.file_size},
		)
		doc.save(ignore_permissions=True)

		result = cleanup_attachments(name, [unused.name, claimed.name])

		self.assertEqual(result, {"removed": [unused.name]})
		self.assertFalse(frappe.db.exists("File", unused.name))
		self.assertTrue(frappe.db.exists("File", claimed.name))

	def test_cleanup_before_session_creation_keeps_other_users_files(self):
		own = frappe.get_doc(
			{"doctype": "File", "file_name": "draft.txt", "content": "draft", "is_private": 1}
		).insert()
		other = frappe.get_doc(
			{"doctype": "File", "file_name": "other.txt", "content": "other", "is_private": 1}
		).insert()
		frappe.db.set_value("File", other.name, "owner", OTHER)
		result = cleanup_attachments(attachments=[own.name, other.name])
		self.assertEqual(result, {"removed": [own.name]})
		self.assertTrue(frappe.db.exists("File", other.name))

	def test_an_admitted_attachment_is_owned_by_its_session(self):
		name = self.create()
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "claimed.txt", "content": "claimed", "is_private": 1}
		).insert()

		api.run(name, "read it", [file.name])

		self.assertEqual(
			frappe.db.get_value(
				"File",
				file.name,
				["attached_to_doctype", "attached_to_name", "attached_to_field"],
			),
			("Flow Session", name, "attachments"),
		)

	def test_sync_repairs_an_attachment_whose_file_was_deleted(self):
		name = self.create()
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "gone.txt", "content": "gone", "is_private": 1}
		).insert()
		api.run(name, "read it", [file.name])
		frappe.db.delete("File", {"name": file.name})

		api.sync_session(name)

		self.assertFalse(frappe.db.exists("Flow Session Attachment", {"parent": name, "file": file.name}))

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
		# Frappe itself refuses an answers value that is neither text nor an object
		for answers in ("nope", "[1]"):
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

	def test_a_system_manager_views_others_trigger_sessions_only_and_writes_only_their_own(self):
		manager = _ensure_manager()
		frappe.set_user(_ensure_user(OTHER))
		chat = self.create()
		fired = new_session(self.agent.name, source="Trigger").name
		self.assertFalse(api.session(fired)["read_only"])
		frappe.set_user(manager)

		with self.assertRaises(frappe.PermissionError):
			api.session(chat)
		self.assertTrue(api.session(fired)["read_only"])
		api.entries(fired)
		self.assertTrue(api.sync_session(fired)["read_only"])
		for call in (
			lambda: api.run(fired, "hi"),
			lambda: api.resume(fired, "{}"),
			lambda: api.abort(fired),
			lambda: api.cancel_pending(fired),
			lambda: api.set_model(fired, self.model.name),
			lambda: api.set_title(fired, "x"),
			lambda: api.set_auto_approve(fired, 1),
			lambda: api.cleanup_attachments(fired),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

		own = self.create()
		self.assertFalse(api.session(own)["read_only"])
		self.assertEqual(api.run(own, "hi")["status"], "started")
		with self.assertRaises(frappe.PermissionError):
			api.delete_session(chat)

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

	def test_list_sessions_names_the_model_in_force(self):
		picked = frappe.get_doc(_model_doc(title="Picked Model")).insert()
		on_agent = self.create(title="On the agent's model")
		on_pick = self.create(title="On its own model", model=picked.name)
		models = {row.name: row.model for row in api.list_sessions()}
		self.assertEqual(models[on_agent], self.model.name)
		self.assertEqual(models[on_pick], picked.name)

	def test_list_sessions_escapes_like_wildcards_in_the_query(self):
		percent = self.create(title="100% done")
		self.create(title="100 percent done")
		underscore = self.create(title="a_b")
		self.create(title="aXb")
		self.assertEqual([row.name for row in api.list_sessions("100%")], [percent])
		self.assertEqual([row.name for row in api.list_sessions("a_b")], [underscore])
		self.assertEqual(len(api.list_sessions("done")), 2)

	def test_list_sessions_continues_past_the_last_row_shown(self):
		names = [self.create(title=f"Paged {i}") for i in range(3)]
		for i, name in enumerate(names):
			frappe.db.set_value(
				"Flow Session", name, "modified", f"2026-02-0{i + 1} 00:00:00", update_modified=False
			)
		first = api.list_sessions("Paged", limit=2)
		self.assertEqual([row.name for row in first], [names[2], names[1]])
		# the browser sends the timestamp back as text
		rest = api.list_sessions("Paged", limit=2, before=str(first[-1].modified))
		self.assertEqual([row.name for row in rest], [names[0]])

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

	def test_run_syncs_again_when_a_run_ends_own_sync_commits_first(self):
		# a queued message goes out the moment a run ends, beside that run's own syncs
		name = self.create()
		real_sync = FlowSession.sync
		syncs = []

		def sync(doc):
			syncs.append(doc.name)
			if len(syncs) == 1:
				raise frappe.TimestampMismatchError
			return real_sync(doc)

		with patch.object(FlowSession, "sync", sync), patch.object(frappe.db, "rollback"):
			self.assertEqual(api.run(name, "hi")["status"], "started")
		self.assertEqual(self.daemon.calls[-1], ("run", name, "hi"))

	def test_run_takes_attachments_as_a_json_list(self):
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "notes.txt", "content": "the body", "is_private": 1}
		).insert()
		name = self.create()
		api.run(name, "read", attachments=json.dumps([file_doc.name]))
		self.assertEqual(
			self.daemon.calls[-1], ("run", name, 'read\n<file name="notes.txt">\nthe body\n</file>')
		)
		self.assertEqual(frappe.db.count("Flow Session Attachment", {"parent": name}), 1)

	def test_run_refuses_a_malformed_attachment_list(self):
		name = self.create()
		for bad in ("not json", json.dumps([1]), json.dumps({"a": 1}), json.dumps([""])):
			with self.assertRaisesRegex(frappe.ValidationError, "Attachments must be a list"):
				api.run(name, "hi", attachments=bad)
		self.assertEqual([c for c in self.daemon.calls if c[0] == "run"], [])

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

	def test_resume_answers_a_sub_agents_batch_while_the_run_keeps_running(self):
		self.daemon.answer = child_pause
		name = self.create()
		run = api.run(name, "look it up")["run"]
		self.daemon.running = True  # the turn goes on while its sub-agent waits
		self.assertEqual(api.sync_session(name)["runs"][0]["status"], "Running")
		self.assertEqual(
			api.resume(name, '{"c9": "Approve"}', approval_seq="8"), {"run": run, "status": "started"}
		)
		self.assertEqual(self.daemon.calls[-1], ("resume", name, {"c9": "Approve"}, 8))
		self.assertEqual(self.run_status(run), "Running")

	def test_abort_cancel_and_entries_pass_through(self):
		name = self.create()
		self.assertEqual(api.abort(name), {"status": "idle"})
		self.assertEqual(api.cancel_pending(name), {"status": "idle"})
		api.run(name, "hi")
		self.assertEqual(api.entries(name, since="2")["entries"][0]["seq"], 3)
		self.assertEqual(self.daemon.calls[-1], ("entries", name, 2, "active"))

	def test_set_model_passes_the_reasoning_effort_to_the_flow_server(self):
		name = self.create()
		self.assertEqual(
			api.set_model(name, self.model.name, reasoning_effort="high"),
			{"model": self.model.name, "reasoning_effort": "high"},
		)
		self.assertEqual(self.daemon.calls[-1][3]["reasoning_effort"], "high")
		self.assertEqual(api.set_model(name, self.model.name, reasoning_effort="")["reasoning_effort"], None)
		self.assertIsNone(self.daemon.calls[-1][3]["reasoning_effort"])
		with self.assertRaisesRegex(frappe.ValidationError, "Reasoning effort must be one of"):
			api.set_model(name, self.model.name, reasoning_effort="extreme")

	def test_settings_persist_on_the_session(self):
		name = self.create()
		other = frappe.get_doc(_model_doc(title="Endpoint Other Model")).insert()
		self.assertEqual(
			api.set_model(name, f" {other.name} "),
			{"model": other.name, "reasoning_effort": None},
		)
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

	def test_skills_lists_what_a_user_may_start_in_a_session_or_with_an_agent(self):
		frappe.get_doc(
			{
				"doctype": "Flow Skill",
				"title": "Expense Approval",
				"description": "How to review a claim.",
				"instructions": "Check the receipt.",
				"user_invocable": 1,
			}
		).insert()
		self.agent.append("skills", {"skill": "Expense Approval"})
		self.agent.save()
		expected = {"skills": [{"name": "expense-approval", "description": "How to review a claim."}]}
		self.assertEqual(api.skills(session=self.create()), expected)
		self.assertEqual(api.skills(agent=self.agent.name), expected)
		# a non-text agent is Frappe's own type error now
		for bad in ({}, {"agent": " "}):
			with self.assertRaisesRegex(frappe.ValidationError, "Session or agent"):
				api.skills(**bad)

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
