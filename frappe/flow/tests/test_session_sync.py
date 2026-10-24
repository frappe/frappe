# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import Mock, call, patch

import frappe
from frappe.flow.api import api
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.lib import session as sessions
from frappe.flow.tests.test_fake_daemon import (
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
from frappe.tests import IntegrationTestCase

ON_COMPLETE = "frappe.flow.tests.test_session_sync.ended"


def ended(run):
	"""What the tests point on_complete at; each test patches it."""


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

	def messages(self, session=None):
		return [(m.role, m.content, m.run) for m in (session or self.session).messages]

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

	def test_text_that_looks_like_html_is_recorded_as_written(self):
		code = 'File "<frozen runpy>", line 198\nif qty > 0 and a & b:'
		run = self.placeholder(message=code)
		rows = [
			row(1, "run_started", run_id="r1"),
			row(2, "user_message", content=code),
			row(3, "assistant_message", content=text(code)),
			row(4, "run_ended", reason="done"),
		]
		self.sync(FakeDaemon(rows))
		run.reload()
		self.assertEqual((run.input, run.output), (code, code))
		self.assertEqual([m.content for m in self.session.messages], [code, code])

	def test_each_sync_reads_only_what_is_new_and_a_rewind_drops_what_followed_its_target(self):
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

		# back to before the second message, and the next turn follows on from there
		third = self.placeholder(message="instead")
		daemon.rows += [row(17, "rewind", target_seq=8), *turn(18, "r3", message="instead")]
		self.sync(daemon)
		second.reload()
		third.reload()
		self.assertEqual(
			[(m.seq, m.content) for m in self.session.messages],
			[
				(2, "hi"),
				(3, "Reading."),
				(5, "[]"),
				(6, "done"),
				(19, "instead"),
				(20, "Reading."),
				(22, "[]"),
				(23, "done"),
			],
		)
		self.assertEqual((second.status, third.daemon_run_id, third.status), ("Completed", "r3", "Completed"))

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

		# read in one sync, a pause and its resume stay one run too
		session = self.new_session()
		run = self.placeholder(session, message="delete it")
		self.sync(FakeDaemon(pause(1, "r1") + resumed(6, "r2")), session)
		run.reload()
		self.assertEqual((run.status, run.daemon_run_id), ("Completed", "r2"))
		self.assertEqual(frappe.db.count("Flow Run", {"session": session.name}), 1)

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

	def test_a_run_that_has_not_ended_follows_the_servers_state(self):
		# still going, dropped by the server, or the session lost along with it
		for state, status, error, run_id, title in (
			({"running": True}, "Running", None, "r1", TITLE),
			({"running": False}, "Failed", sessions.ABANDONED, "r1", TITLE),
			({"missing": True}, "Failed", sessions.GONE, None, None),
		):
			with self.subTest(**state):
				session = self.new_session()
				run = self.placeholder(session)
				self.sync(FakeDaemon(turn(1, "r1")[:2], **state), session)
				run.reload()
				self.assertEqual((run.status, run.error, run.daemon_run_id), (status, error, run_id))
				self.assertEqual(session.title, title)
				self.assertEqual(self.messages(session), [("user", "hi", run.name)] if run_id else [])
		with self.assertRaisesRegex(frappe.ValidationError, "500"):
			self.sync(FakeDaemon(broken=self.session.name))

	def test_rows_go_to_the_oldest_open_run_and_a_steered_message_stays_in_its_run(self):
		first = self.placeholder(message="one")
		second = self.placeholder(message="two")
		rows = [
			*turn(1, "r1", "one")[:2],
			row(3, "user_message", content="and this"),
			*turn(1, "r1", "one")[2:],
			*turn(1, "r2", "two"),
		]
		for seq, entry in enumerate(rows, start=1):
			entry["seq"] = seq
		self.sync(FakeDaemon(rows))
		first.reload()
		second.reload()
		self.assertEqual((first.daemon_run_id, first.status, first.input), ("r1", "Completed", "one"))
		self.assertEqual((second.daemon_run_id, second.status), ("r2", "Completed"))
		self.assertEqual(self.messages()[:2], [("user", "one", first.name), ("user", "and this", first.name)])
		self.assertEqual(frappe.db.count("Flow Run", {"session": self.session.name}), 2)

	def test_a_sync_that_loses_to_a_concurrent_one_runs_again_once_in_a_new_transaction(self):
		for error in (frappe.TimestampMismatchError, frappe.QueryDeadlockError):
			session = Mock(**{"sync.side_effect": [error, None]})
			with self.subTest(error=error.__name__), patch.object(frappe.db, "rollback") as rollback:
				sessions.sync_with_retry(session)
				rollback.assert_called_once_with()
				# no reload: sync must take the lock before anything is read
				self.assertEqual(session.method_calls, [call.sync(), call.sync()])
		session = Mock(**{"sync.side_effect": frappe.TimestampMismatchError})
		with patch.object(frappe.db, "rollback"), self.assertRaises(frappe.TimestampMismatchError):
			sessions.sync_with_retry(session)
		self.assertEqual(session.sync.call_count, 2)

	def test_a_run_whose_placeholder_was_rolled_back_is_recovered(self):
		session = self.new_session(source="Trigger")
		daemon = FakeDaemon(turn(1, "r1", message="first"))
		daemon.turns = 1
		# the next chat records it before starting its own run
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			second = session.chat("second")
			session.sync()
		first = frappe.get_doc("Flow Run", {"session": session.name, "daemon_run_id": "r1"})
		self.assertEqual(
			(first.input, first.source, first.status, first.output), ("first", "Trigger", "Completed", "done")
		)
		second.reload()
		self.assertEqual((second.input, second.daemon_run_id, second.status), ("second", "r2", "Completed"))

	def test_a_pause_stays_open_until_the_server_is_idle(self):
		old = self.placeholder(message="delete it")
		daemon = self.sync(FakeDaemon(pause(1, "r1")))
		# rows logged after the pause, such as a cancelled call, stay with the paused run
		cancelled = '{"status": "cancelled"}'
		daemon.rows.append(
			row(6, "tool_result", tool_call_id="c9", name="delete", content=cancelled, is_error=True)
		)
		self.sync(daemon)
		old.reload()
		self.assertEqual(old.status, "Paused")
		self.assertEqual(self.messages()[-1], ("tool", cancelled, old.name))

		# an idle server closes the stale pause before the next run
		daemon.paused = False
		daemon.turns = 1
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			new = self.session.chat("next")
			self.session.sync()
		old.reload()
		new.reload()
		self.assertEqual((old.status, old.error), ("Failed", sessions.STOPPED))
		self.assertEqual((new.daemon_run_id, new.status, new.input), ("r2", "Completed", "next"))

	def test_the_title_follows_the_server(self):
		self.session.db_set("title", "Renamed")
		self.sync(FakeDaemon(title="Renamed"))
		self.assertEqual(self.session.title, "Renamed")
		self.sync(FakeDaemon(title="Generated"))
		self.assertEqual(self.session.title, "Generated")
		self.sync(FakeDaemon(title=None))
		self.assertEqual(self.session.title, "Generated")

	def test_on_complete_is_called_once_the_run_ends_and_only_once(self):
		daemon = FakeDaemon(answer=lambda seq, run_id, message: turn(seq, run_id, message)[:2])
		with patch.object(DaemonClient, "for_site", return_value=daemon), patch(ON_COMPLETE) as on_complete:
			run = self.session.chat("hi", on_complete=ON_COMPLETE)
			daemon.running = True
			self.session.sync()
			sessions.call_on_complete(self.session)
			on_complete.assert_not_called()
			daemon.rows, daemon.running = turn(1, "r1"), False
			self.session.sync()
			sessions.call_on_complete(self.session)
			sessions.call_on_complete(self.session)
		on_complete.assert_called_once()
		ended_run = on_complete.call_args.args[0]
		self.assertEqual(
			(ended_run.name, ended_run.status, ended_run.output), (run.name, "Completed", "done")
		)
		self.assertIsNone(frappe.db.get_value("Flow Run", run.name, "on_complete"))

	def test_recording_a_runs_end_never_calls_on_complete(self):
		run = self.placeholder()
		run.db_set("on_complete", ON_COMPLETE)
		daemon = FakeDaemon(turn(1, "r1"))
		daemon.turns = 1
		with patch.object(DaemonClient, "for_site", return_value=daemon), patch(ON_COMPLETE) as on_complete:
			# a chat records the ended run before its own turn
			self.session.chat("next")
			run.reload()
			self.assertEqual((run.status, run.on_complete), ("Completed", ON_COMPLETE))
			# opening the session syncs too
			api.session(self.session.name)
			on_complete.assert_not_called()
			sessions.call_on_complete(self.session)
		self.assertEqual(on_complete.call_args.args[0].name, run.name)

	def test_a_failing_on_complete_is_logged_and_its_writes_undone(self):
		run = self.placeholder()
		run.db_set("on_complete", ON_COMPLETE)

		def fail(run):
			frappe.db.set_value("Flow Session", run.session, "title", "Changed")
			raise RuntimeError("boom")

		with patch(ON_COMPLETE, side_effect=fail), patch("frappe.log_error") as log_error:
			self.sync(FakeDaemon(turn(1, "r1"), title=None))
			sessions.call_on_complete(self.session)
		run.reload()
		self.assertEqual((run.status, run.on_complete), ("Completed", None))
		self.assertIsNone(frappe.db.get_value("Flow Session", self.session.name, "title"))
		self.assertEqual(log_error.call_args.kwargs["reference_name"], run.name)

	def test_a_paused_run_refuses_a_rewind_and_cancelling_it_calls_on_complete(self):
		run = self.placeholder(message="delete it")
		run.db_set("on_complete", ON_COMPLETE)
		daemon = self.sync(FakeDaemon(pause(1, "r1")))
		with patch.object(DaemonClient, "for_site", return_value=daemon), patch(ON_COMPLETE) as on_complete:
			with self.assertRaisesRegex(frappe.ValidationError, "paused for approval"):
				self.session.rewind(0)
			run.reload()
			self.assertEqual(run.status, "Paused")
			self.session.cancel_pending()
		self.assertEqual(on_complete.call_args.args[0].status, "Failed")

	def test_a_steered_message_gives_a_run_its_first_on_complete_only(self):
		run = self.placeholder()
		daemon = FakeDaemon(turn(1, "r1")[:2], running=True)
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			joined = self.session.chat("and this", on_complete=ON_COMPLETE)
			self.session.chat("and that", on_complete="frappe.flow.tests.test_session_sync.other")
		self.assertEqual(joined.name, run.name)
		self.assertEqual(frappe.db.get_value("Flow Run", run.name, "on_complete"), ON_COMPLETE)
