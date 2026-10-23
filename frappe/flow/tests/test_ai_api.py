# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow import api
from frappe.flow.api import attach_file, cleanup_attachments, submit_feedback
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.doctype.flow_session.flow_session import FlowSession
from frappe.flow.doctype.flow_session_attachment.test_flow_session_attachment import png_bytes
from frappe.flow.lib.session import new_session
from frappe.flow.memory import store as memory_store
from frappe.flow.permissions import FLOW_USER_ROLE
from frappe.flow.tests.test_fake_daemon import PENDING, FakeDaemon, child_pause, pause
from frappe.flow.tests.test_live_server import LiveServerCase
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase
from frappe.utils import get_url

OTHER = "api-other-user@example.com"
MANAGER = "api-manager@example.com"
SHARER = "api-share-owner@example.com"


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

	def test_attach_file_stages_the_upload_for_the_next_turn(self):
		from frappe.flow.doctype.flow_session_attachment.flow_session_attachment import staged_attachment

		file_doc = self._file()
		chip = attach_file(f"  {file_doc.name}  ")

		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(chip["file_name"], "report.txt")
		self.assertNotIn("extracted_text", chip)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "report body")

		# an image is not OCRed when no model rules it out
		image = self._file(file_name="pic.png", content=png_bytes())
		with patch(
			"frappe.flow.doctype.flow_session_attachment.flow_session_attachment.extract_file"
		) as extract:
			self.assertEqual(attach_file(image.name)["file_name"], "pic.png")
		extract.assert_not_called()
		data = staged_attachment(image.name)
		self.assertIsNone(data["extracted_text"])
		self.assertNotIn("ocr_text", data)

	def test_attach_file_refuses_what_it_cannot_stage(self):
		unsupported = self._file(file_name="data.bin", content="x").name
		for file, error in (
			("", "File is required"),
			("   ", "File is required"),
			(unsupported, "Unsupported file type"),
		):
			with self.subTest(file=file), self.assertRaisesRegex(frappe.ValidationError, error):
				attach_file(file)


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


def _portal_user(email: str) -> str:
	"""A website user, such as a customer."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	return email


def _desk_user(email: str) -> str:
	"""A desk user without Flow's roles."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	frappe.db.set_value("User", email, "user_type", "System User")
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

	def test_feedback_on_a_finished_run_is_recorded_and_cleared(self):
		run = self._run()
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Up")

		# a thumbs-down comment is saved as agent memory until the rating is withdrawn
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual((doc.feedback_rating, doc.feedback_comment), ("Down", "Widget A maps to WGT-001."))
		memory = frappe.get_doc("Flow Agent Memory", result["memory"])
		self.assertEqual(
			(memory.agent, memory.scope, memory.source, memory.source_run, memory.content),
			(self.agent.name, "Agent", "Feedback", run, "Widget A maps to WGT-001."),
		)
		self.assertEqual(submit_feedback(run, "None"), {"rating": None, "forgotten": 1})
		self.assertFalse(frappe.db.exists("Flow Agent Memory", memory.name))
		doc.reload()
		self.assertFalse(doc.feedback_rating)
		self.assertIsNone(doc.feedback_comment)
		self.assertEqual(submit_feedback(run, "None"), {"rating": None})

		# a denied run is finished too
		self.assertEqual(submit_feedback(self._run(status="Denied"), "Up"), {"rating": "Up"})

	def test_only_a_commented_thumbs_down_on_a_memory_agent_saves_memory(self):
		plain = frappe.get_doc(_agent_doc(self.model.name, title="Feedback No Memory Agent")).insert()
		for agent, rating, comment in (
			(self.agent.name, "Up", "Nice."),
			(self.agent.name, "Down", None),
			(plain.name, "Down", "Fix it."),
		):
			with self.subTest(agent=agent, rating=rating, comment=comment):
				run = self._run(agent=agent)
				self.assertNotIn("memory", submit_feedback(run, rating, comment=comment))
				self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), rating)
				self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": agent}))

	def test_refuses_invalid_feedback(self):
		for status, rating, comment, error in (
			("Completed", "Sideways", None, "Rating"),
			("Running", "Up", None, "finished"),
			("Completed", "Down", "x" * 501, "characters"),
		):
			run = self._run(status=status)
			with self.subTest(error), self.assertRaisesRegex(frappe.ValidationError, error):
				submit_feedback(run, rating, comment=comment)

	def test_only_someone_who_may_write_to_the_chat_rates_its_runs(self):
		run = self._run()
		session = frappe.db.get_value("Flow Run", run, "session")
		stranger = _ensure_user("feedback-other-user@example.com")
		reader = _ensure_user("feedback-read-only@example.com")
		frappe.share.add("Flow Run", run, reader, read=1, write=0)
		viewer = _ensure_user("feedback-viewer@example.com")
		frappe.share.add("Flow Session", session, viewer)
		frappe.set_user(viewer)
		# a viewer's sync records a run the site had no row for, so they own that row
		recorded = frappe.get_doc(
			{"doctype": "Flow Run", "session": session, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		for user, name, rating, comment in (
			(stranger, run, "Up", None),
			(reader, run, "Up", None),
			(viewer, recorded.name, "Down", "Not my chat."),
		):
			frappe.set_user(user)
			with self.subTest(user), self.assertRaises(frappe.PermissionError):
				submit_feedback(name, rating, comment=comment)


class ApiCase(IntegrationTestCase):
	"""A model, an agent and a scripted flow server behind the endpoints."""

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		# a failed send writes an Error Log, which a rollback keeps
		self.enterContext(
			patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email")
		)
		self.model = frappe.get_doc(_model_doc(title="Endpoint Model")).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name, title="Endpoint Agent")).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def create(self, **fields) -> str:
		return api.create_session(self.agent.name, **fields)["name"]

	def run_status(self, run: str) -> str:
		return frappe.db.get_value("Flow Run", run, "status")

	def upload(self, file_name: str, content: str):
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
		).insert()


class TestSessionEndpoints(ApiCase):
	def test_every_endpoint_is_whitelisted(self):
		for name in api.__all__:
			frappe.is_whitelisted(frappe.get_attr(f"frappe.flow.api.{name}"))

	def test_boot_lists_what_a_client_needs_and_the_users_rights(self):
		from frappe.flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant

		sync_builtin_assistant(self.model.name)
		hidden = frappe.get_doc(_agent_doc(self.model.name, title="Hidden Agent", enabled=0)).insert()
		data = api.boot()
		agents = {row.name: row.model for row in data["agents"]}
		self.assertEqual(agents.get(self.agent.name), self.model.name)
		self.assertNotIn(hidden.name, agents)
		self.assertEqual(data["default_agent"], ASSISTANT_AGENT_TITLE)
		model = next(row for row in data["models"] if row.name == self.model.name)
		self.assertEqual(model.model_id, "openai/gpt-4o-mini")
		self.assertIn("context_window", model)
		self.assertIn("txt", data["file_types"])
		self.assertEqual(data["user"]["name"], "Administrator")
		self.assertIn("full_name", data["user"])
		self.assertEqual(data["permissions"]["Flow Provider"], ["read", "write", "create", "delete"])
		frappe.db.delete("Flow Provider")  # tearDown rolls it back
		self.assertFalse(api.boot()["has_provider"])
		frappe.get_doc({"doctype": "Flow Provider", "provider": "openai"}).insert()
		self.assertTrue(api.boot()["has_provider"])
		frappe.set_user(_ensure_user(OTHER))
		data = api.boot()
		self.assertEqual(data["user"]["name"], OTHER)
		self.assertEqual(data["permissions"]["Flow Provider"], [])
		self.assertEqual(data["permissions"]["Flow Model"], ["read"])

	def test_create_session_names_the_agent_and_keeps_auto_approve(self):
		data = api.create_session(self.agent.name, model=self.model.name, title=" Hello ", auto_approve="1")
		self.assertEqual(
			(
				data["agent"],
				data["model"],
				data["title"],
				data["source"],
				data["auto_approve"],
				data["owner"],
				data["runs"],
			),
			(self.agent.name, self.model.name, "Hello", "Manual", True, "Administrator", []),
		)
		config = self.daemon.configs[data["name"]]
		self.assertEqual(
			(config["session_id"], config["title"], config["model"], config["auto_approve"]),
			(data["name"], "Hello", "openai/gpt-4o-mini", True),
		)
		plain = api.create_session(self.agent.name)
		self.assertFalse(plain["auto_approve"])
		# no pick: the chat keeps the agent's model it started on, as the flow server does
		self.assertEqual(frappe.db.get_value("Flow Session", plain["name"], "model"), self.model.name)
		self.agent.db_set("model", frappe.get_doc(_model_doc(title="Next Agent Model")).insert().name)
		self.assertEqual(api.session(plain["name"])["model"], self.model.name)
		self.model.db_set("enabled", 0)  # the chat's own model is the one checked
		with self.assertRaisesRegex(frappe.ValidationError, "is disabled"):
			api.run(plain["name"], "hi")

	def test_cleanup_deletes_only_the_callers_unclaimed_uploads(self):
		name = self.create()
		unused, claimed, draft, other = (
			self.upload(f"{label}.txt", label) for label in ("unused", "claimed", "draft", "other")
		)
		doc = frappe.get_doc("Flow Session", name)
		doc.append(
			"attachments",
			{"file": claimed.name, "file_name": claimed.file_name, "file_size": claimed.file_size},
		)
		doc.save(ignore_permissions=True)
		frappe.db.set_value("File", other.name, "owner", OTHER)

		self.assertEqual(cleanup_attachments(name, [unused.name, claimed.name]), {"removed": [unused.name]})
		self.assertFalse(frappe.db.exists("File", unused.name))
		self.assertTrue(frappe.db.exists("File", claimed.name))
		# before a session exists, another user's upload stays too
		self.assertEqual(cleanup_attachments(attachments=[draft.name, other.name]), {"removed": [draft.name]})
		self.assertTrue(frappe.db.exists("File", other.name))

	def test_run_sends_attached_files_and_claims_them_for_the_session(self):
		notes = self.upload("notes.txt", "the body")
		name = self.create()
		run = api.run(name, "read", attachments=json.dumps([notes.name]))["run"]
		self.assertEqual(
			self.daemon.calls[-1], ("run", name, 'read\n<file name="notes.txt">\nthe body\n</file>')
		)
		self.assertEqual(frappe.db.get_value("Flow Run", run, "input"), "read")
		[row] = frappe.get_doc("Flow Session", name).attachments
		self.assertEqual(
			(row.file, row.file_name, row.run, row.mode, row.extracted_text),
			(notes.name, "notes.txt", run, "Inline", "the body"),
		)
		self.assertEqual(
			frappe.db.get_value(
				"File",
				notes.name,
				["attached_to_doctype", "attached_to_name", "attached_to_field"],
			),
			("Flow Session", name, "attachments"),
		)

		# a file may go without a message
		gone = self.upload("gone.txt", "gone")
		self.assertEqual(api.run(name, "", attachments=[gone.name])["status"], "started")
		self.assertEqual(self.daemon.calls[-1], ("run", name, '\n<file name="gone.txt">\ngone\n</file>'))
		# a sync drops the row of a file deleted since
		frappe.db.delete("File", {"name": gone.name})
		api.sync_session(name)
		self.assertEqual([row.file for row in frappe.get_doc("Flow Session", name).attachments], [notes.name])

	def test_blank_or_malformed_input_is_refused(self):
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
		for bad in ("not json", json.dumps([1]), json.dumps({"a": 1}), json.dumps([""])):
			with self.assertRaisesRegex(frappe.ValidationError, "Attachments must be a list"):
				api.run(name, "hi", attachments=bad)
		self.assertEqual([c for c in self.daemon.calls if c[0] == "run"], [])

	def test_sessions_are_for_their_owner(self):
		manager, other = _ensure_manager(), _ensure_user(OTHER)
		frappe.set_user(_ensure_user(SHARER))
		chat = self.create()
		fired = new_session(self.agent.name, source="Trigger").name
		self.assertFalse(api.session(fired)["read_only"])

		frappe.set_user(other)
		for call in (
			lambda: api.session(chat),
			lambda: api.run(chat, "hi"),
			lambda: api.set_title(chat, "x"),
			lambda: api.delete_session(chat),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		self.assertEqual(api.list_sessions(), [])

		# a System Manager views others' trigger sessions only, and writes only their own
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
			lambda: api.rewind(fired, 0),
			lambda: api.compact(fired),
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

	def test_an_owner_shares_a_chat_to_view_only_and_takes_it_back(self):
		owner, viewer = _ensure_user(SHARER), _ensure_user(OTHER)
		member = _ensure_user("api-share-member@example.com")
		desk, portal = _desk_user("api-open-desk@example.com"), _portal_user("api-open-portal@example.com")
		manager = _ensure_manager()
		frappe.set_user(owner)
		name = self.create(title="Q3 plan")
		for grant in ({"write": 1}, {"share": 1}):
			with (
				self.subTest(grant),
				self.assertRaisesRegex(frappe.ValidationError, "only be shared to view"),
			):
				frappe.share.add("Flow Session", name, viewer, **grant)
		# Desk's "Everyone" would reach portal users too: General access opens a chat instead
		with self.assertRaisesRegex(frappe.ValidationError, "General access"):
			frappe.share.add("Flow Session", name, everyone=1)
		self.assertEqual([row.name for row in api.share_session(name, viewer)], [viewer])
		self.assertEqual([row.name for row in api.list_shares(name)], [viewer])
		self.assertEqual(api.session(name)["general_access"], "Restricted")

		frappe.set_user(viewer)
		data = api.session(name)
		self.assertTrue(data["read_only"])
		self.assertEqual(data["owner_name"], frappe.db.get_value("User", owner, "full_name"))
		api.entries(name)
		self.assertNotIn(name, [row.name for row in api.list_sessions()])
		for call in (
			lambda: api.run(name, "hi"),
			lambda: api.set_title(name, "x"),
			lambda: api.delete_session(name),
			lambda: api.list_shares(name),
			lambda: api.share_session(name, viewer),
			lambda: api.unshare_session(name, viewer),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

		# General access opens it to every Flow user to view
		frappe.set_user(owner)
		with self.assertRaises(frappe.ValidationError):
			api.set_general_access(name, "Public")
		self.assertEqual(api.set_general_access(name, "Everyone"), "Everyone")
		self.assertEqual(api.session(name)["general_access"], "Everyone")
		frappe.set_user(member)
		self.assertTrue(api.session(name)["read_only"])
		api.entries(name)
		# opened by its link, not listed among their own chats
		self.assertNotIn(name, [row.name for row in api.list_sessions()])
		for call in (
			lambda: api.run(name, "hi"),
			lambda: api.list_shares(name),
			lambda: api.set_general_access(name, "Restricted"),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		# not people without Flow: Frappe's own check refuses them, so its REST API does too
		frappe.set_user("Administrator")
		for user in (desk, portal):
			with self.subTest(user):
				self.assertFalse(frappe.has_permission("Flow Session", "read", name, user=user))
		# a System Manager may read it like any Flow user, but not delete it
		self.assertTrue(frappe.has_permission("Flow Session", "read", name, user=manager))
		self.assertFalse(frappe.has_permission("Flow Session", "delete", name, user=manager))

		# taking both back has the live relay recheck who follows the chat
		frappe.set_user(owner)
		frappe.db.after_commit.reset()  # leave only the removals' work queued
		with (
			patch("frappe.flow.doctype.flow_session.flow_session._redis_url", return_value="redis://relay"),
			patch("redis.Redis.from_url") as connect,
		):
			self.assertEqual(api.unshare_session(name, viewer), [])
			api.set_general_access(name, "Restricted")
			# the relay asks the site again, so only once the removal is saved
			connect.return_value.publish.assert_not_called()
			frappe.db.after_commit.run()
		publish = connect.return_value.publish
		self.assertEqual(
			{call.args[0] for call in publish.call_args_list}, {f"flow-access:{frappe.local.site}"}
		)
		# it names who lost the view, or no one when general access closes, and the owner it leaves alone
		self.assertEqual(
			[json.loads(call.args[1]) for call in publish.call_args_list],
			[
				{"session": name, "user": viewer, "owner": owner},
				{"session": name, "user": None, "owner": owner},
			],
		)
		for user in (viewer, member):
			frappe.set_user(user)
			with self.subTest(user), self.assertRaises(frappe.PermissionError):
				api.session(name)

	def test_a_shared_chat_notifies_each_viewer_once_with_a_link_to_it(self):
		viewer = _ensure_user(OTHER)
		# Administrator's name is not its email, which is how Frappe finds a recipient
		frappe.get_doc("User", "Administrator").add_roles(FLOW_USER_ROLE)
		frappe.set_user(_ensure_user(SHARER))
		name = self.create(title="<b>Q3</b>")
		for user in (viewer, viewer, "Administrator"):
			api.share_session(name, user)
		logs = frappe.get_all(
			"Notification Log",
			filters={"document_name": name},
			fields=["for_user", "type", "subject", "link"],
			order_by="for_user asc",
		)
		self.assertEqual([log.for_user for log in logs], ["Administrator", viewer])
		self.assertEqual((logs[1].type, logs[1].link), ("Share", get_url(f"/flow/s/{name}")))
		self.assertIn("&lt;b&gt;Q3&lt;/b&gt;", logs[1].subject)

	def test_a_chat_is_shared_only_with_active_flow_users(self):
		name = self.create()
		found = _ensure_user("api-share-found@example.com")
		frappe.db.set_value("User", found, "full_name", "Quentin Sharefound")
		disabled = _ensure_user("api-share-disabled@example.com")
		frappe.db.set_value("User", disabled, "enabled", 0)
		manager, desk = _ensure_manager(), _desk_user("api-share-desk@example.com")
		# found by name or email; a System Manager may use Flow without the Flow User role
		self.assertEqual([row.name for row in api.find_users("Quentin")], [found])
		self.assertEqual([row.name for row in api.find_users("api-share-found@")], [found])
		self.assertEqual([row.name for row in api.find_users(manager)], [manager])
		self.assertEqual(api.find_users(desk), [])
		for user in ("api-share-nobody@example.com", "Guest", disabled, desk):
			with self.subTest(user), self.assertRaises(frappe.ValidationError):
				api.share_session(name, user)
		# a filter in place of a user: newer Frappe refuses it by type, before our own check
		with self.assertRaises((frappe.ValidationError, frappe.FrappeTypeError)):
			api.share_session(name, ["like", "%"])
		self.assertEqual(api.list_shares(name), [])
		self.assertEqual([row.name for row in api.share_session(name, manager)], [manager])
		frappe.db.set_value("User", found, "enabled", 0)
		self.assertEqual(api.find_users("Quentin"), [])

	def test_list_sessions_shows_own_manual_sessions_newest_first(self):
		picked = frappe.get_doc(_model_doc(title="Picked Model")).insert()
		first = self.create(title="First")
		on_agents_model = self.create(title="On the agent's model")
		second = self.create(title="Second", model=picked.name)
		trigger = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "source": "Trigger", "title": "Fired"}
		).insert()
		frappe.db.set_value("Flow Session", first, "modified", "2026-01-01 00:00:00", update_modified=False)
		frappe.set_user(_ensure_user(OTHER))
		foreign = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "title": "Theirs"}
		).insert()
		frappe.set_user("Administrator")

		rows = api.list_sessions()
		names = [row.name for row in rows]
		self.assertEqual(names[0], second)
		self.assertNotIn(trigger.name, names)
		self.assertNotIn(foreign.name, names)
		self.assertEqual(set(rows[0].keys()), {"name", "title", "agent", "model", "modified"})
		self.assertEqual([row.name for row in api.list_sessions(limit=1)], [second])
		# the model in force: the chat's own pick, else its agent's
		models = {row.name: row.model for row in rows}
		self.assertEqual((models[second], models[on_agents_model]), (picked.name, self.model.name))
		with self.subTest("an older chat"):
			# the test site keeps older committed sessions, so only the newest position is fixed
			self.assertIn(first, names)

	def test_list_sessions_narrows_by_title_and_continues_past_the_last_row_shown(self):
		percent = self.create(title="100% done")
		spelled = self.create(title="100 percent done")
		underscore = self.create(title="a_b")
		self.create(title="aXb")
		# like wildcards in the query match only themselves
		self.assertEqual([row.name for row in api.list_sessions("100%")], [percent])
		self.assertEqual([row.name for row in api.list_sessions("a_b")], [underscore])
		frappe.db.set_value("Flow Session", percent, "modified", "2026-02-01 00:00:00", update_modified=False)
		frappe.db.set_value("Flow Session", spelled, "modified", "2026-02-02 00:00:00", update_modified=False)
		first = api.list_sessions("done", limit=1)
		self.assertEqual([row.name for row in first], [spelled])
		# the browser sends the timestamp back as text
		rest = api.list_sessions("done", before=str(first[-1].modified))
		self.assertEqual([row.name for row in rest], [percent])

	def test_run_answers_started_and_a_sync_completes_the_run(self):
		name = self.create()
		started = api.run(name, "hi")
		self.assertEqual(started["status"], "started")
		placeholder = frappe.get_doc("Flow Run", started["run"])
		self.assertEqual(
			(
				placeholder.session,
				placeholder.input,
				placeholder.source,
				placeholder.status,
				placeholder.output,
				placeholder.iterations,
				placeholder.daemon_run_id,
			),
			(name, "hi", "Manual", "Running", None, 0, None),
		)
		self.assertEqual(self.daemon.calls[-1], ("run", name, "hi"))
		# its rows wait for the next sync
		self.assertEqual(frappe.db.count("Flow Session Message", {"parent": name}), 0)

		# opening the session syncs a run still open, and nothing once all are settled
		self.daemon.calls.clear()
		data = api.session(name)
		self.assertEqual(self.daemon.calls[0], ("get_session", name))
		self.assertEqual(
			[(run.name, run.status, run.error) for run in data["runs"]], [(started["run"], "Completed", None)]
		)
		self.assertEqual(data["title"], self.daemon.title)
		self.daemon.calls.clear()
		self.assertEqual(api.session(name), data)
		self.assertEqual(self.daemon.calls, [])
		# sync_session always syncs, and records nothing twice
		self.assertEqual(api.sync_session(name), data)
		self.assertEqual(frappe.db.count("Flow Run", {"session": name}), 1)
		self.assertEqual(frappe.db.count("Flow Session Message", {"parent": name}), 4)

	def test_verbs_sync_again_when_a_concurrent_sync_commits_first(self):
		# e.g. a queued message goes out the moment a run ends, beside that run's own syncs
		real_sync = FlowSession.sync

		def losing_first_sync(error):
			syncs = []

			def sync(doc):
				syncs.append(doc.name)
				if len(syncs) == 1:
					raise error
				return real_sync(doc)

			return patch.object(FlowSession, "sync", sync)

		self.daemon.answer = pause
		name = self.create()
		with patch.object(frappe.db, "rollback"):
			with losing_first_sync(frappe.TimestampMismatchError):
				run = api.run(name, "delete it")
			self.assertEqual(run["status"], "started")
			self.assertEqual(self.daemon.calls[-1], ("run", name, "delete it"))
			with losing_first_sync(frappe.TimestampMismatchError):
				self.assertEqual(
					api.resume(name, '{"c9": "Approve"}'), {"run": run["run"], "status": "started"}
				)
			self.assertEqual(self.run_status(run["run"]), "Running")
			second = api.run(name, "delete that")["run"]
			with losing_first_sync(frappe.QueryDeadlockError):
				self.assertEqual(api.cancel_pending(name), {"status": "cancelled"})
		self.assertEqual(
			frappe.db.get_value("Flow Run", second, ["status", "error"]), ("Failed", "Stopped by user.")
		)

	def test_run_answers_steered_with_the_active_run(self):
		self.daemon.answer = lambda seq, run_id, message: []
		name = self.create()
		first = api.run(name, "hi")["run"]
		self.daemon.running = True
		self.assertEqual(api.run(name, "and this"), {"run": first, "status": "steered"})
		self.assertEqual(self.daemon.calls[-1], ("run", name, "and this"))
		self.assertEqual(frappe.db.count("Flow Run", {"session": name}), 1)

	def test_resume_answers_the_paused_run(self):
		self.daemon.answer = pause
		name = self.create()
		with self.assertRaisesRegex(frappe.ValidationError, "no paused run"):
			api.resume(name, '{"c1": "Approve"}')
		run = api.run(name, "delete it")["run"]
		self.assertEqual(api.sync_session(name)["runs"][0]["status"], "Paused")
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual((doc.approval_seq, json.loads(doc.questions)), (4, [PENDING]))
		self.assertEqual(api.resume(name, '{"c9": "Approve"}'), {"run": run, "status": "started"})
		self.assertEqual(
			[c for c in self.daemon.calls if c[0] == "resume"], [("resume", name, {"c9": "Approve"}, 4)]
		)
		doc.reload()
		self.assertEqual((doc.status, doc.approval_seq), ("Running", 0))
		self.assertFalse(doc.questions)
		self.assertEqual(api.sync_session(name)["runs"][0]["status"], "Completed")
		self.assertEqual(frappe.db.count("Flow Run", {"session": name}), 1)

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

	def test_rewind_branches_the_chat_and_never_reads_a_bad_target_as_the_start(self):
		name = self.create()
		api.run(name, "hi")
		self.assertEqual(api.rewind(name, "0"), {"status": "rewound"})
		self.assertEqual(frappe.get_doc("Flow Session", name).messages, [])
		for bad in ("abc", "-1", "", "²"):
			with self.assertRaisesRegex(frappe.ValidationError, "whole number"):
				api.rewind(name, bad)
		self.assertEqual([c for c in self.daemon.calls if c[0] == "rewind"], [("rewind", name, 0)])
		# a link on another site can't rewind a chat: GET skips Frappe's CSRF check
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.rewind], ("POST",))

	def test_a_compaction_is_a_manual_run_of_its_own_and_a_refused_one_leaves_none(self):
		name = new_session(self.agent.name, source="Trigger").name
		with self.assertRaisesRegex(frappe.ValidationError, "nothing to compact"):
			api.compact(name)
		api.run(name, "hi")
		api.sync_session(name)
		started = api.compact(name)
		self.assertEqual((started["status"], self.run_status(started["run"])), ("started", "Running"))

		api.sync_session(name)
		run = frappe.get_doc("Flow Run", started["run"])
		self.assertEqual(
			(run.input, run.source, run.status, run.daemon_run_id), ("/compact", "Manual", "Completed", "r2")
		)
		self.assertEqual(json.loads(run.usage)["input_tokens"], 40)
		self.assertEqual(len(frappe.get_doc("Flow Session", name).messages), 4)  # the summary adds none
		self.daemon.running = True
		with self.assertRaisesRegex(frappe.ValidationError, "a run is already active"):
			api.compact(name)
		self.assertEqual(frappe.db.count("Flow Run", {"session": name, "input": "/compact"}), 1)
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.compact], ("POST",))

	def test_abort_cancel_and_entries_pass_through(self):
		name = self.create()
		self.assertEqual(api.abort(name), {"status": "idle"})
		self.assertEqual(api.cancel_pending(name), {"status": "idle"})
		api.run(name, "hi")
		self.assertEqual(api.entries(name, since="2")["entries"][0]["seq"], 3)
		self.assertEqual(self.daemon.calls[-1], ("entries", name, 2, "active"))
		self.daemon.running = True
		self.assertEqual(api.abort(name), {"status": "aborting"})

	def test_set_model_sends_the_models_credentials_and_reasoning_effort(self):
		name = self.create()
		other = frappe.get_doc(
			_model_doc(
				title="Endpoint Other Model",
				model_id="openai/gpt-4o",
				api_key="sk-other",
				base_url="https://other.example.com",
				extra_params='{"provider": {"zdr": true}}',
			)
		).insert()
		self.assertEqual(
			api.set_model(name, f" {other.name} ", reasoning_effort="high"),
			{"model": other.name, "reasoning_effort": "high"},
		)
		self.assertEqual(
			self.daemon.calls[-1],
			(
				"set_model",
				name,
				"openai/gpt-4o",
				{
					"api_key": "sk-other",
					"api_base": "https://other.example.com",
					"model_params": {"provider": {"zdr": True}},
					"reasoning_effort": "high",
				},
			),
		)
		self.assertEqual(frappe.db.get_value("Flow Session", name, "model"), other.name)
		self.assertEqual(api.set_model(name, other.name, reasoning_effort="")["reasoning_effort"], None)
		self.assertIsNone(self.daemon.calls[-1][3]["reasoning_effort"])
		with self.assertRaisesRegex(frappe.ValidationError, "Reasoning effort must be one of"):
			api.set_model(name, other.name, reasoning_effort="extreme")

		# a model saved on the record, as from Desk, reaches the server too; other saves don't
		session = frappe.get_doc("Flow Session", name)
		session.model = self.model.name
		session.save()
		self.assertEqual(self.daemon.calls[-1][:3], ("set_model", name, "openai/gpt-4o-mini"))
		session.title = "Renamed in Desk"
		session.save()

		other.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			api.set_model(name, other.name)
		self.assertEqual(len([c for c in self.daemon.calls if c[0] == "set_model"]), 3)

	def test_title_and_auto_approve_persist_on_both_sides(self):
		name = self.create()
		self.assertEqual(api.set_title(name, "  Renamed  "), {"title": "Renamed"})
		self.assertEqual(api.set_auto_approve(name, "1"), {"auto_approve": True})
		doc = frappe.get_doc("Flow Session", name)
		self.assertEqual((doc.title, doc.auto_approve), ("Renamed", 1))
		self.assertEqual(api.set_auto_approve(name, 0), {"auto_approve": False})
		self.assertEqual(api.session(name)["auto_approve"], False)
		self.assertEqual(
			[c for c in self.daemon.calls if c[0] == "patch_config"],
			[
				("patch_config", name, {"title": "Renamed"}),
				("patch_config", name, {"auto_approve": True}),
				("patch_config", name, {"auto_approve": False}),
			],
		)
		self.assertEqual(self.daemon.configs[name]["auto_approve"], False)

		# a trigger session always auto-approves
		fired = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "source": "Trigger", "auto_approve": 0}
		).insert()
		self.assertTrue(fired.auto_approve)
		with self.assertRaisesRegex(frappe.ValidationError, "always auto-approve"):
			api.set_auto_approve(fired.name, 0)
		self.assertEqual(api.set_auto_approve(fired.name, 1), {"auto_approve": True})

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

	def test_delete_session_needs_the_flow_servers_consent(self):
		name, lost = self.create(), self.create()
		with patch("frappe.flow.knowledge.attachment_store.delete"):
			self.daemon.running = True
			with self.assertRaisesRegex(frappe.ValidationError, "409"):
				api.delete_session(name)
			self.assertTrue(frappe.db.exists("Flow Session", name))
			self.daemon.running = False
			self.assertEqual(api.delete_session(name), {"status": "deleted"})
			# a session the flow server no longer has goes too
			self.daemon.missing = True
			self.assertEqual(api.delete_session(lost), {"status": "deleted"})
		self.assertFalse(frappe.db.exists("Flow Session", name))
		self.assertFalse(frappe.db.exists("Flow Session", lost))
		self.assertEqual(
			[c for c in self.daemon.calls if c[0] == "delete_session"],
			[("delete_session", name), ("delete_session", name), ("delete_session", lost)],
		)


class TestLiveEndpoints(LiveServerCase):
	def test_a_rewind_takes_the_chat_back_to_before_a_message_and_the_next_turn_branches_there(self):
		name = api.create_session(self.agent.name)["name"]
		started = frappe.call("frappe.flow.api.run", session=name, message="one")
		# the run answers with its placeholder at once
		self.assertEqual(started["status"], "started")
		self.assertEqual(frappe.db.get_value("Flow Run", started["run"], "status"), "Running")
		self.wait_idle(name)
		frappe.call("frappe.flow.api.run", session=name, message="two")
		self.wait_idle(name)
		two = next(row for row in api.entries(name)["entries"] if row.get("content") == "two")
		# the page's target: the entry before the message's run_started
		self.assertEqual(api.rewind(name, two["parent_seq"] - 1), {"status": "rewound"})
		frappe.call("frappe.flow.api.run", session=name, message="three")
		self.wait_idle(name)
		data = api.sync_session(name)

		self.assertEqual([run.status for run in data["runs"]], ["Completed"] * 3)
		self.assertEqual(data["title"], "one")
		self.assertEqual(frappe.db.get_value("Flow Run", started["run"], "output"), "Mock reply to: one")
		entries = api.entries(name)["entries"]
		self.assertEqual(entries[-1]["type"], "run_ended")
		self.assertEqual(
			[row["content"] for row in entries if row["type"] == "user_message"],
			["one", "three"],
		)
		self.assertEqual(
			[(m.role, m.content) for m in frappe.get_doc("Flow Session", name).messages],
			[
				("user", "one"),
				("assistant", "Mock reply to: one"),
				("user", "three"),
				("assistant", "Mock reply to: three"),
			],
		)

	def test_a_manual_compaction_summarizes_the_chat_and_the_next_turn_goes_on(self):
		name = api.create_session(self.agent.name)["name"]
		frappe.call("frappe.flow.api.run", session=name, message="one")
		self.wait_idle(name)
		compacting = api.compact(name)["run"]
		self.wait_idle(name)
		frappe.call("frappe.flow.api.run", session=name, message="two")
		self.wait_idle(name)
		data = api.sync_session(name)

		self.assertEqual([run.status for run in data["runs"]], ["Completed"] * 3)
		self.assertEqual(data["runs"][1].name, compacting)
		self.assertEqual(frappe.db.get_value("Flow Run", compacting, "input"), "/compact")
		self.assertIn("compaction", [row["type"] for row in api.entries(name)["entries"]])
		self.assertEqual(
			[(m.role, m.content) for m in frappe.get_doc("Flow Session", name).messages],
			[
				("user", "one"),
				("assistant", "Mock reply to: one"),
				("user", "two"),
				("assistant", "Mock reply to: two"),
			],
		)
