# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.daemon.client import DaemonClient
from flow.lib import session as sessions
from flow.tests.test_fake_daemon import (
	PENDING,
	TITLE,
	FakeDaemon,
	child_pause,
	pause,
	resumed,
	row,
	text,
	turn,
)


class TestSync(IntegrationTestCase):
	"""The log recorder: the flow server's log rows become Flow Runs and transcript rows."""

	def setUp(self):
		self.model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Sync Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Sync Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		self.session = self.new_session()

	def tearDown(self):
		frappe.db.rollback()

	def new_session(self, source="Manual"):
		return frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "source": source}
		).insert()

	def placeholder(self, session=None, message="hi"):
		doc = {
			"doctype": "Flow Run",
			"session": (session or self.session).name,
			"source": "Manual",
			"input": message,
			"status": "Running",
		}
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	def sync(self, daemon, session=None):
		session = session or self.session
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			session.sync()
		session.reload()
		return daemon

	def messages(self):
		return [(m.role, m.content, m.run) for m in self.session.messages]

	def test_a_finished_turn_lands_on_the_placeholder(self):
		run = self.placeholder()
		daemon = self.sync(FakeDaemon(turn(1, "r1")))
		run.reload()
		self.assertEqual(
			(run.daemon_run_id, run.status, run.output, run.iterations, run.error),
			("r1", "Completed", "done", 2, None),
		)
		self.assertEqual(
			json.loads(run.tool_calls), [{"id": "c1", "name": "read", "arguments": {"doctype": "ToDo"}}]
		)
		self.assertEqual(
			json.loads(run.usage),
			{
				"input_tokens": 30,
				"output_tokens": 7,
				"cache_read_tokens": 8,
				"cache_write_tokens": 0,
				"cost": 0.75,
			},
		)
		self.assertEqual(
			self.messages(),
			[
				("user", "hi", run.name),
				("assistant", "Reading.", run.name),
				("tool", "[]", run.name),
				("assistant", "done", run.name),
			],
		)
		self.assertEqual(
			json.loads(self.session.messages[1].tool_calls),
			[
				{
					"id": "c1",
					"type": "function",
					"function": {"name": "read", "arguments": '{"doctype": "ToDo"}'},
				}
			],
		)
		self.assertEqual(self.session.messages[2].tool_call_id, "c1")
		self.assertEqual((self.session.last_synced_seq, self.session.title), (8, TITLE))
		self.assertEqual(
			daemon.calls, [("get_session", self.session.name), ("entries", self.session.name, 0, "all")]
		)

	def test_a_sync_reads_only_what_is_new(self):
		self.placeholder()
		daemon = self.sync(FakeDaemon(turn(1, "r1")))
		self.sync(daemon)
		self.assertEqual(len(self.messages()), 4)
		self.assertEqual(
			[c for c in daemon.calls if c[0] == "entries"], [("entries", self.session.name, 0, "all")]
		)
		second = self.placeholder(message="again")
		daemon.rows += turn(9, "r2", message="again")
		self.sync(daemon)
		second.reload()
		self.assertEqual((second.daemon_run_id, second.status, second.input), ("r2", "Completed", "again"))
		self.assertEqual(len(self.messages()), 8)
		self.assertEqual(daemon.calls[-1], ("entries", self.session.name, 8, "all"))
		self.assertEqual(self.session.last_synced_seq, 16)

	def test_a_pause_keeps_the_batch_and_a_resume_continues_the_same_run(self):
		run = self.placeholder(message="delete it")
		daemon = self.sync(FakeDaemon(pause(1, "r1")))
		run.reload()
		self.assertEqual((run.status, run.daemon_run_id, run.approval_seq), ("Paused", "r1", 4))
		self.assertEqual(json.loads(run.questions), [PENDING])
		daemon.rows += resumed(6, "r2")
		self.sync(daemon)
		run.reload()
		self.assertEqual(
			(run.status, run.daemon_run_id, run.iterations, run.output), ("Completed", "r2", 2, "Gone.")
		)
		self.assertFalse(run.questions)
		self.assertFalse(run.approval_seq)
		self.assertEqual(frappe.db.count("Flow Run", {"session": self.session.name}), 1)
		self.assertEqual([m[0] for m in self.messages()], ["user", "assistant", "tool", "assistant"])

	def test_a_sub_agents_rows_stay_out_of_the_run_and_only_its_usage_counts(self):
		run = self.placeholder(message="look it up")
		child = {"subagent_id": "c1"}
		rows = [
			*child_pause(1, "r1"),
			row(10, "run_started", run_id="r1-c1b", **child),
			row(11, "tool_result", tool_call_id="c9", name="delete", content="Deleted 1 ToDo", **child),
			row(12, "assistant_message", content=text("Gone."), **child),
			row(13, "usage", input_tokens=3, output_tokens=1, **child),
			row(14, "run_ended", reason="done", **child),
			row(15, "tool_result", tool_call_id="c1", name="subagent", content="Gone.\n\n[subagent_id: c1]"),
			row(16, "assistant_message", content=text("Done.")),
			row(17, "usage", input_tokens=20, output_tokens=2),
			row(18, "run_ended", reason="done"),
		]
		self.sync(FakeDaemon(rows))
		run.reload()
		self.assertEqual(
			(run.status, run.daemon_run_id, run.iterations, run.output), ("Completed", "r1", 2, "Done.")
		)
		self.assertFalse(run.questions)
		self.assertEqual(frappe.db.count("Flow Run", {"session": self.session.name}), 1)
		self.assertEqual(
			[m[:2] for m in self.messages()],
			[
				("user", "look it up"),
				("assistant", None),
				("tool", "Gone.\n\n[subagent_id: c1]"),
				("assistant", "Done."),
			],
		)
		self.assertEqual(json.loads(run.usage)["input_tokens"], 33)
		self.assertEqual(self.session.last_synced_seq, 18)

	def test_a_pause_and_its_resume_in_one_sync_stay_one_run(self):
		run = self.placeholder(message="delete it")
		self.sync(FakeDaemon(pause(1, "r1") + resumed(6, "r2")))
		run.reload()
		self.assertEqual((run.status, run.daemon_run_id), ("Completed", "r2"))
		self.assertEqual(frappe.db.count("Flow Run", {"session": self.session.name}), 1)

	def test_how_a_run_ends_decides_its_status(self):
		cases = [
			("done", None, "Completed", None),
			("length", None, "Completed", None),
			("denied", None, "Denied", None),
			("aborted", None, "Failed", "Stopped by user."),
			("max_turns", None, "Failed", "The agent hit its iteration limit."),
			("budget", None, "Failed", "The agent hit its output token budget."),
			("error", "ProviderError: bad key", "Failed", "ProviderError: bad key"),
		]
		for reason, message, status, error in cases:
			with self.subTest(reason=reason):
				session = self.new_session()
				run = self.placeholder(session)
				rows = [row(1, "run_started", run_id="r"), row(2, "user_message", content="hi")]
				if message:
					rows.append(row(3, "run_error", message=message))
				rows.append(row(4, "run_ended", reason=reason))
				self.sync(FakeDaemon(rows), session)
				run.reload()
				self.assertEqual((run.status, run.error), (status, error))

	def test_a_run_the_server_dropped_is_failed(self):
		run = self.placeholder()
		self.sync(FakeDaemon(turn(1, "r1")[:2], running=False))
		run.reload()
		self.assertEqual((run.status, run.error), ("Failed", sessions.ABANDONED))
		self.assertEqual(self.messages(), [("user", "hi", run.name)])

	def test_a_run_still_going_is_left_alone(self):
		run = self.placeholder()
		self.sync(FakeDaemon(turn(1, "r1")[:2], running=True))
		run.reload()
		self.assertEqual((run.status, run.daemon_run_id), ("Running", "r1"))

	def test_a_message_steered_into_a_run_stays_inside_it(self):
		run = self.placeholder()
		rows = [*turn(1, "r1")[:2], row(3, "user_message", content="and this"), *turn(1, "r1")[2:]]
		for seq, entry in enumerate(rows, start=1):
			entry["seq"] = seq
		self.sync(FakeDaemon(rows))
		run.reload()
		self.assertEqual((run.status, run.input), ("Completed", "hi"))
		self.assertEqual(self.messages()[:2], [("user", "hi", run.name), ("user", "and this", run.name)])
		self.assertEqual(frappe.db.count("Flow Run", {"session": self.session.name}), 1)

	def test_a_session_the_server_lost_fails_its_running_run(self):
		run = self.placeholder()
		self.sync(FakeDaemon(missing=True))
		run.reload()
		self.assertEqual((run.status, run.error), ("Failed", sessions.GONE))
		self.assertIsNone(self.session.title)

	def test_a_server_error_surfaces(self):
		with self.assertRaisesRegex(frappe.ValidationError, "500"):
			self.sync(FakeDaemon(broken=self.session.name))

	def test_sync_recovers_a_run_whose_placeholder_was_rolled_back(self):
		session = self.new_session(source="Trigger")
		self.sync(FakeDaemon(turn(1, "r1", message="from trigger")), session)
		run = frappe.get_doc("Flow Run", {"session": session.name})
		self.assertEqual(
			(run.daemon_run_id, run.input, run.source, run.status, run.output),
			("r1", "from trigger", "Trigger", "Completed", "done"),
		)

	def test_chat_recovers_a_missing_placeholder_before_starting_the_next_run(self):
		daemon = FakeDaemon(turn(1, "r1", message="first"))
		daemon.turns = 1
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			second = self.session.chat("second")
			self.session.sync()
		second.reload()
		first = frappe.get_doc("Flow Run", {"session": self.session.name, "daemon_run_id": "r1"})
		self.assertEqual((first.input, first.status), ("first", "Completed"))
		self.assertEqual((second.input, second.daemon_run_id, second.status), ("second", "r2", "Completed"))

	def test_rows_after_a_pause_stay_with_the_paused_run(self):
		run = self.placeholder(message="delete it")
		daemon = self.sync(FakeDaemon(pause(1, "r1")))
		cancelled = '{"status": "cancelled"}'
		daemon.rows.append(
			row(6, "tool_result", tool_call_id="c9", name="delete", content=cancelled, is_error=True)
		)
		self.sync(daemon)
		run.reload()
		self.assertEqual(run.status, "Paused")
		self.assertEqual(self.messages()[-1], ("tool", cancelled, run.name))

	def test_an_idle_server_closes_a_stale_pause_before_the_next_run(self):
		old = self.placeholder(message="delete it")
		daemon = self.sync(FakeDaemon(pause(1, "r1")))
		old.reload()
		self.assertEqual(old.status, "Paused")

		daemon.paused = False
		daemon.turns = 1
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			new = self.session.chat("next")
			self.session.sync()

		old.reload()
		new.reload()
		self.assertEqual((old.status, old.error), ("Failed", sessions.STOPPED))
		self.assertEqual((new.daemon_run_id, new.status, new.input), ("r2", "Completed", "next"))

	def test_two_placeholders_are_matched_oldest_first(self):
		first = self.placeholder(message="one")
		second = self.placeholder(message="two")
		self.sync(FakeDaemon(turn(1, "r1", "one") + turn(9, "r2", "two")))
		first.reload()
		second.reload()
		self.assertEqual((first.daemon_run_id, second.daemon_run_id), ("r1", "r2"))
		self.assertEqual((first.status, second.status), ("Completed", "Completed"))

	def test_the_title_follows_the_server(self):
		self.session.db_set("title", "Renamed")
		self.sync(FakeDaemon(title="Renamed"))
		self.assertEqual(self.session.title, "Renamed")
		self.sync(FakeDaemon(title="Generated"))
		self.assertEqual(self.session.title, "Generated")
		self.sync(FakeDaemon(title=None))
		self.assertEqual(self.session.title, "Generated")
