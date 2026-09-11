# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from flow.daemon.callback import callback, confirm_title
from flow.daemon.client import DaemonClient
from flow.lib.tool import tool
from flow.tests.fake_daemon import FakeDaemon, turn
from flow.tools.builtins import sync_builtin_tools

SECRET = "callback-secret"
OWNER = "callback-owner@example.com"
MODULE = "flow.tests.test_daemon_callback"
BOOM = "def main(reason: str) -> str:\n\traise ValueError(reason)\n"


@tool
def whoami() -> str:
	"""The user this tool runs as."""
	return frappe.session.user


@tool
def current_run() -> str | None:
	"""The run flag while a tool runs."""
	return frappe.flags.flow_run


@tool
def insert_then_fail() -> None:
	"""Inserts a ToDo, then raises."""
	frappe.get_doc({"doctype": "ToDo", "description": "callback-rollback"}).insert(ignore_permissions=True)
	raise ValueError("after insert")


class TestToolCallback(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def setUp(self):
		sync_builtin_tools()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": SECRET}))
		if not frappe.db.exists("User", OWNER):
			frappe.get_doc(
				{"doctype": "User", "email": OWNER, "first_name": "Callback", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		for slug in ("whoami", "current_run", "insert_then_fail"):
			self.flow_tool(slug, type="Imported", import_path=f"{MODULE}.{slug}")
		self.flow_tool("boom", type="Script", code=BOOM)
		model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Callback Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		attached = (
			"read",
			"delete",
			"execute",
			"update_memory",
			"search_attachments",
			"whoami",
			"current_run",
			"insert_then_fail",
			"boom",
		)
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Callback Agent",
				"model": model.name,
				"instructions": "Be terse.",
				"tools": [{"tool": slug} for slug in attached],
				"enabled": 1,
			}
		).insert()
		self.session = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert()
		self.session.db_set("owner", OWNER)

	def tearDown(self):
		frappe.db.rollback()

	def flow_tool(self, slug: str, **fields) -> None:
		doc = {
			"doctype": "Flow Tool",
			"title": slug,
			"slug": slug,
			"description": slug,
			"enabled": 1,
			**fields,
		}
		frappe.get_doc(doc).insert()

	def call(
		self, name: str, args: dict | None = None, *, mode="execute", token=SECRET, session=None
	) -> dict:
		"""What the daemon posts. Identity comes from the session, not user_context."""
		payload = {
			"callback_type": "tool",
			"session_id": session or self.session.name,
			"tool": name,
			"args": args or {},
			"user_context": {"site": frappe.local.site, "user": "Administrator"},
			"mode": mode,
		}
		headers = {"X-Harness-Token": token} if token is not None else {}
		set_request(method="POST", json=payload, headers=headers)
		try:
			return frappe.call(callback, **payload)
		finally:
			del frappe.local.request

	def call_terminal(self, seq: int, *, token=SECRET) -> dict:
		payload = {
			"callback_type": "run_ended",
			"session_id": self.session.name,
			"terminal_seq": seq,
		}
		set_request(method="POST", json=payload, headers={"X-Harness-Token": token})
		try:
			return frappe.call(callback, **payload)
		finally:
			del frappe.local.request

	def test_a_wrong_or_missing_token_is_401(self):
		self.assertEqual(frappe.AuthenticationError.http_status_code, 401)
		for token in ("wrong", "", None):
			with self.subTest(token=token), self.assertRaises(frappe.AuthenticationError):
				self.call("whoami", token=token)
		with patch.dict(frappe.local.conf, {"flow_server_secret": None}):
			with self.assertRaises(frappe.AuthenticationError):
				self.call("whoami")

	def test_tools_run_as_the_sessions_owner_never_as_user_context(self):
		self.assertEqual(self.call("whoami"), {"content": OWNER, "is_error": False})
		self.assertEqual(frappe.session.user, "Administrator")

	def test_terminal_callback_synchronizes_once_and_duplicate_delivery_is_safe(self):
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": self.session.name, "source": "Manual", "status": "Running"}
		).insert()
		daemon = FakeDaemon(rows=turn(1, "daemon-run", "hello"))
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			self.assertEqual(self.call_terminal(8), {"synced_through": 8})
			self.assertEqual(self.call_terminal(8), {"synced_through": 8})
		run.reload()
		self.assertEqual((run.status, run.daemon_run_id, run.output), ("Completed", "daemon-run", "done"))
		self.session.reload()
		self.assertEqual(self.session.last_synced_seq, 8)
		self.assertEqual(len(self.session.messages), 4)

	def test_terminal_recovery_creates_the_run_as_the_session_owner(self):
		daemon = FakeDaemon(rows=turn(1, "daemon-run", "hello"))
		frappe.set_user("Guest")
		try:
			with patch.object(DaemonClient, "for_site", return_value=daemon):
				self.assertEqual(self.call_terminal(8), {"synced_through": 8})
			self.assertEqual(frappe.session.user, "Guest")
		finally:
			frappe.set_user("Administrator")
		run = frappe.get_doc("Flow Run", {"session": self.session.name})
		self.assertEqual(run.owner, OWNER)

	def test_the_owners_permissions_apply(self):
		result = self.call("read", {"doctype": "Error Log"})
		self.assertTrue(result["is_error"])
		self.assertIn("Permission", result["content"])
		self.assertEqual(frappe.session.user, "Administrator")

	def test_update_memory_never_reaches_the_daemon_and_is_unknown_here(self):
		names = [tool.name for tool in self.agent.client_tools()]
		self.assertNotIn("update_memory", names)
		self.assertIn("whoami", names)
		result = self.call("update_memory", {"content": "remember this", "scope": "agent"})
		self.assertEqual(result, {"content": "Unknown tool update_memory.", "is_error": True})

	def test_search_attachments_is_bound_to_the_calling_session(self):
		hit = {"attachment": "F1", "content": "refunds within thirty days", "score": 0.9}
		with patch("flow.knowledge.retriever.retrieve_attachments", return_value=[hit]) as retrieve:
			result = self.call("search_attachments", {"query": "refund"})
		self.assertEqual(retrieve.call_args.kwargs["session"], self.session.name)
		self.assertEqual(
			json.loads(result["content"]),
			[{"file": None, "content": "refunds within thirty days", "score": 0.9}],
		)

	def test_an_unknown_session_or_a_disabled_owner_is_an_error(self):
		result = self.call("whoami", session="nope")
		self.assertEqual(result, {"content": "Unknown session nope.", "is_error": True})
		frappe.db.set_value("User", OWNER, "enabled", 0)
		result = self.call("whoami")
		self.assertEqual(result, {"content": "The session's owner is disabled.", "is_error": True})

	def test_an_unattached_or_disabled_tool_is_unknown(self):
		result = self.call("create", {"doctype": "ToDo", "records": []})
		self.assertEqual(result, {"content": "Unknown tool create.", "is_error": True})
		frappe.db.set_value("Flow Tool", "boom", "enabled", 0)
		result = self.call("boom", {"reason": "x"})
		self.assertEqual(result, {"content": "Unknown tool boom.", "is_error": True})

	def test_a_disabled_agent_stops_existing_sessions(self):
		self.agent.db_set("enabled", 0)
		self.assertEqual(
			self.call("whoami"), {"content": "The session's agent is disabled.", "is_error": True}
		)

	def test_a_raising_script_tool_is_error_content_and_the_run_goes_on(self):
		self.assertEqual(self.call("boom", {"reason": "kaboom"}), {"content": "kaboom", "is_error": True})
		self.assertEqual(len(self.call("boom", {"reason": "x" * 700})["content"]), 500)
		self.assertEqual(self.call("whoami"), {"content": OWNER, "is_error": False})
		self.assertEqual(frappe.session.user, "Administrator")

	def test_a_failed_tools_writes_are_rolled_back(self):
		self.assertEqual(self.call("insert_then_fail"), {"content": "after insert", "is_error": True})
		self.assertFalse(frappe.db.exists("ToDo", {"description": "callback-rollback"}))

	def test_the_run_flag_names_the_sessions_running_run_while_a_tool_runs(self):
		self.assertEqual(self.call("current_run"), {"content": "", "is_error": False})
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": self.session.name, "source": "Manual", "status": "Running"}
		).insert()
		self.assertEqual(self.call("current_run"), {"content": run.name, "is_error": False})
		self.assertIsNone(frappe.flags.flow_run)

	def test_confirm_mode_names_the_action_then_the_tools_own_summary(self):
		prompt = self.call("delete", {"doctype": "ToDo", "names": ["a", "b"]}, mode="confirm")["prompt"]
		self.assertEqual(prompt, "Delete 2 ToDo records\nDelete 2 ToDo: a, b")
		prompt = self.call("execute", {"code": "result = 1", "description": "Count things"}, mode="confirm")
		self.assertEqual(prompt["prompt"], "Count things\nCount things:\n\nresult = 1")
		prompt = self.call("boom", {"reason": "x"}, mode="confirm")["prompt"]
		self.assertEqual(prompt, 'Boom\n{\n  "reason": "x"\n}')

	def test_confirm_titles_match_the_pages(self):
		cases = [
			("create", {"doctype": "ToDo", "records": [{}, {}, {}]}, "Create 3 ToDo records"),
			("create", {"doctype": "ToDo", "records": []}, "Create 0 ToDo records"),
			("update", {"doctype": "ToDo", "names": ["a"]}, "Update 1 ToDo record"),
			("delete", {"doctype": "ToDo", "names": ["a", "b"]}, "Delete 2 ToDo records"),
			("delete", {"doctype": "ToDo"}, "Delete 1 ToDo record"),
			(
				"run_action",
				{"doctype": "Sales Order", "names": ["a", "b"], "action": "submit"},
				'Run "Submit" on 2 Sales Order',
			),
			("run_action", {"action": "send_sms"}, 'Run "Send sms" on records'),
			("execute", {"description": "  Count things ", "code": ""}, "Count things"),
			("execute", {"code": "x"}, "Run Python code"),
			("create", {"records": []}, "Create"),
			("send_email", {}, "Send email"),
		]
		for name, args, title in cases:
			with self.subTest(name=name, args=args):
				self.assertEqual(confirm_title(name, args), title)
