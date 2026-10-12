# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from flow.api import api
from flow.daemon.callback import JOB_TIMEOUT, START_WITHIN, callback, confirm_title, run_background_tool
from flow.daemon.client import DaemonClient, DaemonError
from flow.lib.tool import ToolContext, tool
from flow.memory import store as memory_store
from flow.tests.test_fake_daemon import FakeDaemon, turn
from flow.tools.builtins import sync_builtin_tools

SECRET = "callback-secret"
OWNER = "callback-owner@example.com"
MODULE = "flow.tests.test_daemon_callback"
BOOM = "def main(reason: str) -> str:\n\traise ValueError(reason)\n"
WHOAMI = "def main() -> str:\n\treturn frappe.session.user\n"


def ended(run):
	"""An on_complete the tests patch."""


@tool
def whoami(*, ctx: ToolContext) -> str:
	"""The user this tool runs as."""
	return frappe.session.user


@tool
def insert_then_fail(*, ctx: ToolContext) -> None:
	"""Inserts a ToDo, then raises."""
	frappe.get_doc({"doctype": "ToDo", "description": "callback-rollback"}).insert(ignore_permissions=True)
	raise ValueError("after insert")


@tool(background=lambda args: args.get("slow"))
def maybe_later(slow: bool = False, *, ctx: ToolContext) -> str:
	"""The user this tool runs as; queued only when slow."""
	return frappe.session.user


@tool
def queue_then_fail(*, ctx: ToolContext) -> None:
	"""Queues work for after commit, as a webhook does, then raises."""
	frappe.db.after_commit.add(lambda: frappe.flags.update(after_commit_ran=True))
	raise ValueError("after queueing")


@tool
def callback_context(*, ctx: ToolContext) -> dict:
	"""Return the trusted identity Flow supplied for this callback."""
	return {"session": ctx.session_id, "agent": ctx.agent, "user": ctx.user}


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
		for slug in (
			"whoami",
			"maybe_later",
			"insert_then_fail",
			"queue_then_fail",
			"callback_context",
		):
			self.flow_tool(slug, type="Imported", import_path=f"{MODULE}.{slug}")
		self.flow_tool("boom", type="Script", code=BOOM)
		self.flow_tool("whoami_later", type="Script", code=WHOAMI, background=1)
		model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Callback Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		attached = (
			"read_records",
			"delete",
			"execute",
			"update_memory",
			"search_attachments",
			"whoami",
			"whoami_later",
			"maybe_later",
			"insert_then_fail",
			"queue_then_fail",
			"callback_context",
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
		self,
		name: str,
		args: dict | None = None,
		*,
		mode="execute",
		token=SECRET,
		session=None,
		agent=None,
		result_token=None,
	) -> dict:
		"""What the daemon posts. Identity comes from the session, not user_context; `agent` is
		what a sub-agent's context names."""
		context = {"site": frappe.local.site, "user": "Administrator"}
		if agent:
			context["agent"] = agent
		payload = {
			"cmd": "flow.daemon.callback.callback",  # frappe's API layer adds this to the arguments
			"callback_type": "tool",
			"session_id": session or self.session.name,
			"tool": name,
			"args": args or {},
			"user_context": context,
			"mode": mode,
		}
		if result_token:
			payload["result_token"] = result_token
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

	def test_a_tool_can_receive_trusted_callback_context(self):
		result = self.call("callback_context")
		self.assertFalse(result["is_error"])
		self.assertEqual(
			json.loads(result["content"]),
			{"session": self.session.name, "agent": self.agent.name, "user": OWNER},
		)

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

	def test_on_complete_is_called_once_as_the_owner_after_the_terminal_sync(self):
		run = frappe.get_doc(
			{
				"doctype": "Flow Run",
				"session": self.session.name,
				"source": "Manual",
				"status": "Running",
				"on_complete": f"{MODULE}.ended",
			}
		).insert()
		calls = []
		daemon = FakeDaemon(rows=turn(1, "daemon-run", "hello"))
		with (
			patch.object(DaemonClient, "for_site", return_value=daemon),
			patch(f"{MODULE}.ended", side_effect=lambda run: calls.append((run.name, frappe.session.user))),
		):
			api.session(self.session.name)  # Administrator opening it records the end, leaves on_complete
			self.assertEqual(calls, [])
			self.call_terminal(8)
			self.call_terminal(8)
		self.assertEqual(calls, [(run.name, OWNER)])

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
		result = self.call("read_records", {"doctype": "Error Log"})
		self.assertTrue(result["is_error"])
		self.assertIn("Permission", result["content"])
		self.assertEqual(frappe.session.user, "Administrator")

	def test_update_memory_runs_as_the_owner_and_names_the_running_run(self):
		self.addCleanup(memory_store.drop_table)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": self.session.name, "source": "Manual", "status": "Running"}
		).insert()
		result = self.call("update_memory", {"content": "Prefers INR.", "scope": "user"})
		self.assertFalse(result["is_error"])
		memory = frappe.get_doc("Flow Agent Memory", json.loads(result["content"])["memory_id"])
		self.assertEqual(
			(memory.agent, memory.scope, memory.user, memory.source_run),
			(self.agent.name, "User", OWNER, run.name),
		)

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

	def test_a_sub_agent_calls_back_with_its_own_tools_and_a_stranger_is_refused(self):
		child = self.flow_agent("Callback Child", tools=[{"tool": "whoami"}])
		stranger = self.flow_agent("Callback Stranger", tools=[{"tool": "whoami"}])
		self.agent.append("sub_agents", {"agent": child})
		self.agent.save()

		self.assertEqual(self.call("whoami", agent=child), {"content": OWNER, "is_error": False})
		self.assertEqual(
			self.call("read_records", {"doctype": "ToDo"}, agent=child),
			{"content": "Unknown tool read_records.", "is_error": True},
		)
		self.assertEqual(
			self.call("whoami", agent=stranger),
			{"content": f"{stranger} is not a sub-agent of {self.agent.name}.", "is_error": True},
		)

	def flow_agent(self, title: str, **fields) -> str:
		doc = {
			"doctype": "Flow Agent",
			"title": title,
			"model": self.agent.model,
			"instructions": "x",
			**fields,
		}
		return frappe.get_doc(doc).insert().name

	def test_a_raising_script_tool_is_error_content(self):
		self.assertEqual(self.call("boom", {"reason": "kaboom"}), {"content": "kaboom", "is_error": True})
		self.assertEqual(frappe.session.user, "Administrator")

	def test_a_long_tool_error_is_cut(self):
		self.assertEqual(len(self.call("boom", {"reason": "x" * 700})["content"]), 500)

	def test_a_failed_tools_writes_are_rolled_back(self):
		self.assertEqual(self.call("insert_then_fail"), {"content": "after insert", "is_error": True})
		self.assertFalse(frappe.db.exists("ToDo", {"description": "callback-rollback"}))

	def test_a_failed_tools_after_commit_work_is_dropped(self):
		frappe.db.after_commit.reset()  # leave only this call's work queued
		self.addCleanup(frappe.flags.pop, "after_commit_ran", None)
		self.assertEqual(self.call("queue_then_fail"), {"content": "after queueing", "is_error": True})
		frappe.db.after_commit.run()
		self.assertFalse(frappe.flags.after_commit_ran)

	def test_a_background_tool_is_queued_and_its_job_posts_the_result(self):
		with patch("frappe.enqueue") as enqueue:
			reply = self.call("whoami_later", result_token="t1")
		self.assertTrue(reply.pop("pending"))
		self.assertGreater(reply["timeout"], START_WITHIN + JOB_TIMEOUT)
		self.assertEqual(enqueue.call_args.args, ("flow.daemon.callback.run_background_tool",))
		job = enqueue.call_args.kwargs
		self.assertEqual((job.pop("queue"), job.pop("timeout")), ("long", JOB_TIMEOUT))

		daemon = FakeDaemon()
		with patch.object(DaemonClient, "for_site", return_value=daemon), patch("frappe.db.commit") as commit:
			run_background_tool(**job)
		commit.assert_called_once()
		self.assertEqual(
			daemon.calls,
			[
				("tool_waiting", self.session.name, "t1"),
				("tool_result", self.session.name, "t1", {"content": OWNER, "is_error": False}),
			],
		)

	def test_a_tool_can_choose_the_background_per_call(self):
		inline = {"content": OWNER, "is_error": False}
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(self.call("maybe_later", {"slow": False}, result_token="t1"), inline)
			enqueue.assert_not_called()
			self.assertTrue(self.call("maybe_later", {"slow": True}, result_token="t2")["pending"])
			enqueue.assert_called_once()
			# the job itself passes no token, so it runs the tool
			self.assertEqual(self.call("maybe_later", {"slow": True}), inline)

	def test_site_config_sets_the_background_tool_timeout(self):
		with (
			patch.dict(frappe.local.conf, {"flow_background_tool_timeout": 3600}),
			patch("frappe.enqueue") as enqueue,
		):
			reply = self.call("whoami_later", result_token="t1")
		self.assertEqual(enqueue.call_args.kwargs["timeout"], 3600)
		self.assertGreater(reply["timeout"], START_WITHIN + 3600)

	def test_a_job_whose_run_stopped_waiting_skips_the_tool(self):
		daemon = FakeDaemon()
		daemon.waiting = False
		with (
			patch.object(DaemonClient, "for_site", return_value=daemon),
			patch("flow.daemon.callback.tool_callback") as tool_callback,
			patch("frappe.db.commit"),
		):
			run_background_tool(self.session.name, "whoami_later", {}, {}, "t1", start_by=time.time() + 60)
		tool_callback.assert_not_called()
		self.assertEqual(daemon.calls, [("tool_waiting", self.session.name, "t1")])

	def test_a_failed_result_delivery_is_retried_then_raised(self):
		daemon = FakeDaemon()
		args = (self.session.name, "whoami_later", {}, {}, "t1")
		with (
			patch.object(DaemonClient, "for_site", return_value=daemon),
			patch("frappe.db.commit"),
			patch("time.sleep") as sleep,
		):
			down = DaemonError(None, "down")
			with patch.object(daemon, "tool_result", side_effect=[down, {"delivered": True}]) as post:
				run_background_tool(*args, start_by=time.time() + 60)
			self.assertEqual(post.call_count, 2)
			with patch.object(daemon, "tool_result", side_effect=down), self.assertRaises(DaemonError):
				run_background_tool(*args, start_by=time.time() + 60)
		self.assertEqual([call.args[0] for call in sleep.call_args_list], [0, 1, 0, 1, 5])

	def test_a_job_that_waited_past_its_start_window_skips_the_tool(self):
		daemon = FakeDaemon()
		with (
			patch.object(DaemonClient, "for_site", return_value=daemon),
			patch("flow.daemon.callback.tool_callback") as tool_callback,
			patch("frappe.db.commit"),
		):
			run_background_tool(self.session.name, "whoami_later", {}, {}, "t1", start_by=time.time() - 1)
		tool_callback.assert_not_called()
		[(verb, session, token, result)] = daemon.calls
		self.assertEqual((verb, session, token), ("tool_result", self.session.name, "t1"))
		self.assertTrue(result["is_error"])
		self.assertIn("waited too long", result["content"])

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
