# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import click

import frappe
from frappe.flow.assistant import ASSISTANT_AGENT_NAME
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.evals import chat
from frappe.flow.evals.case import Case, load_cases
from frappe.flow.evals.play import play
from frappe.flow.evals.report import compare, verdict
from frappe.flow.evals.site import LIST, PREFIX, Snapshot, _checksums, _tables, check_site, lock
from frappe.flow.tests.test_fake_daemon import FakeDaemon, row
from frappe.query_builder.utils import db_type_is
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import run_only_if

USER = "flow-eval-user@example.com"


def make_user():
	if not frappe.db.exists("User", USER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Eval",
				"send_welcome_email": 0,
				"roles": [{"role": "Flow User"}],
			}
		).insert(ignore_permissions=True)


def case(path=None, check=lambda run: None, setup=make_user, ask="hi"):
	return Case("probe", ask, USER, setup, check, path)


class TestCases(IntegrationTestCase):
	def load(self, files: dict[str, str]):
		folder = Path(tempfile.mkdtemp())
		for name, body in files.items():
			(folder / name).write_text(body)
		with patch("frappe.get_app_source_path", return_value=str(folder)):
			return load_cases("frappe")

	def test_a_case_needs_its_four_names_and_a_normal_user(self):
		ok = "ASK = 'hi'\nUSER = 'a@example.com'\ndef setup(): pass\ndef check(run): pass\n"
		self.assertEqual([c.name for c in self.load({"one.py": ok, "_shared.py": "x = 1"})], ["one"])
		with self.assertRaisesRegex(click.ClickException, r"two\.py has no check"):
			self.load({"one.py": ok, "two.py": ok.replace("def check", "def other")})
		with self.assertRaisesRegex(click.ClickException, r"admin\.py: USER must be a normal user"):
			self.load({"admin.py": ok.replace("a@example.com", "Administrator")})

	def test_the_site_must_allow_evals_and_be_on_mariadb(self):
		with patch("frappe.get_file_json", return_value={}):
			self.assertRaisesRegex(click.ClickException, "disabled for the site", check_site)
		with patch("frappe.get_file_json", return_value={"allow_flow_evals": "true"}):
			check_site()
			with patch.dict(frappe.local.conf, {"db_type": "postgres"}):
				self.assertRaisesRegex(click.ClickException, "MariaDB", check_site)

	def test_verdict(self):
		for args, word in (
			((0, 3, 3, 3), "better"),
			((3, 3, 0, 3), "worse"),
			((3, 3, 3, 3), "same"),
			((0, 3, 0, 3), "same"),
			((1, 3, 3, 3), "unclear"),
			((0, 3, 6, 6), "better"),
			((0, 3, 2, 2, 1), "unclear"),
			((0, 0, 3, 3), "unclear"),
		):
			self.assertEqual(verdict(*args), word, args)

	def test_compare_reads_two_saved_runs(self):
		root = Path(tempfile.mkdtemp())
		for label, statuses in (("base", ("fail", "fail", "fail")), ("mine", ("pass", "pass", "pass"))):
			(root / label).mkdir()
			for n, status in enumerate(statuses, 1):
				record = {
					"case": "probe",
					"n": n,
					"label": label,
					"status": status,
					"detail": None if status == "pass" else "no reply",
					"seconds": 10.0,
					"usage": {"input_tokens": 100, "output_tokens": 20, "cost": 0.01},
					"model": {"name": "Luna", "model_id": "openai/gpt-6-luna"},
					"commits": {"frappe": label},
				}
				(root / label / f"probe-{n}.json").write_text(json.dumps(record))
		table = compare(root, "base", "mine")
		self.assertIn("base: openai/gpt-6-luna · frappe base", table)
		self.assertIn("probe                 0/3        3/3        better", table)
		self.assertIn("tokens per run        120        120", table)
		self.assertIn("fail  probe                 base #3  no reply", table)
		self.assertNotIn("warning", table)
		self.assertRaisesRegex(click.ClickException, "Saved: base, mine", compare, root, "base", "other")


@run_only_if(db_type_is.MARIADB)
class SnapshotCase(IntegrationTestCase):
	"""One snapshot of the whole test site for the class; every test is put back by it."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(lock())
		cls.ensure_assistant()
		cls.snapshot = Snapshot()
		cls.snapshot.recover()
		cls.snapshot.take()
		cls.addClassCleanup(cls.snapshot.drop)
		cls.addClassCleanup(cls.snapshot.restore)

	def setUp(self):
		self.addCleanup(self.snapshot.restore)
		self.addCleanup(frappe.set_user, "Administrator")

	@staticmethod
	def ensure_assistant():
		from frappe.flow.assistant import sync_builtin_assistant

		if not frappe.db.exists("Flow Model", {"enabled": 1}):
			frappe.get_doc(
				{"doctype": "Flow Model", "title": "Eval", "model_id": "openai/none", "enabled": 1}
			).insert()
		sync_builtin_assistant()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	def retake(self):
		self.snapshot.drop()
		self.snapshot.take()


class TestSnapshot(SnapshotCase):
	def change_everything(self):
		frappe.get_doc({"doctype": "ToDo", "description": "made in the run"}).insert()
		frappe.db.set_value("User", "Administrator", "bio", "changed in the run")
		frappe.db.delete("Language", {"name": frappe.db.get_value("Language", {})})
		frappe.get_doc(
			{"doctype": "Custom Field", "dt": "ToDo", "fieldname": "eval_probe", "fieldtype": "Data"}
		).insert()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		frappe.db.sql_ddl("create table `tabEval Probe` (name varchar(140) primary key)")

	def test_restore_puts_rows_columns_and_tables_back(self):
		tables = _tables()
		before = _checksums(tables)
		self.change_everything()
		self.assertTrue(frappe.db.has_column("ToDo", "eval_probe"))
		self.assertTrue(self.snapshot.restore())
		self.assertEqual(_tables(), tables)
		self.assertEqual(_checksums(tables), before)
		self.assertFalse(frappe.db.has_column("ToDo", "eval_probe"))

	def test_a_partial_snapshot_is_never_restored_from(self):
		taken = self.snapshot.complete()
		frappe.db.sql(f"delete from `{LIST}` where tbl = ''")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		self.addCleanup(self.retake)
		frappe.db.sql_ddl("create table `tabEval Probe` (name varchar(140) primary key)")
		self.addCleanup(frappe.db.sql_ddl, "drop table if exists `tabEval Probe`")
		self.assertFalse(self.snapshot.restore())
		self.assertIn("tabEval Probe", _tables())
		self.assertIsNone(Snapshot().recover())  # a killed copy: dropped, nothing restored
		self.assertIn("tabEval Probe", _tables())
		self.assertFalse([t for t in _tables(own=False) if t.startswith(LIST)])
		self.assertTrue(taken)

	def test_recover_restores_a_whole_snapshot_and_drops_it(self):
		self.addCleanup(self.retake)
		tables = _tables()
		before = _checksums(tables)
		taken = self.snapshot.complete()
		self.change_everything()
		self.assertEqual(Snapshot().recover(), taken)
		self.assertEqual(_checksums(tables), before)
		self.assertFalse([t for t in _tables(own=False) if t.startswith(LIST)])

	def test_a_table_whose_copy_is_missing_is_left_as_it_is(self):
		self.addCleanup(self.retake)
		copy = frappe.db.sql(f"select copy from `{LIST}` where tbl = 'tabToDo'", pluck=True)[0]
		frappe.db.sql_ddl(f"drop table `{copy}`")
		frappe.get_doc({"doctype": "ToDo", "description": "kept"}).insert()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		self.assertTrue(self.snapshot.restore())
		self.assertTrue(frappe.db.exists("ToDo", {"description": "kept"}))

	def test_a_kill_part_way_through_drop_leaves_nothing_to_restore(self):
		self.addCleanup(self.retake)
		frappe.db.sql(f"delete from `{LIST}` where tbl = ''")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		frappe.db.sql_ddl(f"drop table `{PREFIX}0`")
		self.assertIsNone(Snapshot().recover())
		self.assertFalse([t for t in _tables(own=False) if t.startswith(LIST)])

	def test_the_skill_arm_hides_a_skill_and_the_restore_shows_it_again(self):
		skill = frappe.db.get_value("Flow Skill", {"app": "frappe"})
		self.assertTrue(skill, "frappe ships skills")
		agent = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_NAME)
		self.assertIn(skill, agent.skill_index())
		frappe.db.set_value("Flow Skill", skill, "enabled", 0)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		make_user()
		frappe.set_user(USER)
		self.assertNotIn(skill, agent.skill_index())
		frappe.set_user("Administrator")
		self.snapshot.restore()
		self.assertEqual(frappe.db.get_value("Flow Skill", skill, "enabled"), 1)


class TestCheck(SnapshotCase):
	def test_a_refused_step_fails_unless_it_is_expected(self):
		step = ("read_records", {"doctype": "Error Log"})
		result = play(case(path=[step]))
		self.assertEqual(result["status"], "fail")
		self.assertIn("error: ", result["steps"][0]["detail"])
		self.assertIn("permission", result["steps"][0]["detail"].lower())
		self.snapshot.restore()
		result = play(case(path=[(*step, "ermission")]))
		self.assertEqual(
			(result["status"], result["steps"][0]["word"]), ("pass", "ok (refused, as expected)")
		)

	def test_a_create_step_writes_as_the_case_user(self):
		result = play(
			case(path=[("create", {"doctype": "ToDo", "records": [{"description": "eval probe"}]})])
		)
		self.assertEqual(result["status"], "pass", result)
		self.assertEqual(frappe.db.get_value("ToDo", {"description": "eval probe"}, "owner"), USER)

	def test_an_expect_function_and_a_path_function(self):
		def setup():
			make_user()
			return "eval probe"

		def path(value):
			create = ("create", {"doctype": "ToDo", "records": [{"description": value}]})
			read = ("read_records", {"doctype": "ToDo", "fields": ["description"]})
			return [create, (*read, lambda result: value in result)]

		result = play(case(path=path, setup=setup))
		self.assertEqual([s["word"] for s in result["steps"]], ["ok", "ok"], result)
		self.snapshot.restore()
		result = play(case(path=[("read_records", {"doctype": "ToDo"}, lambda result: False)]))
		self.assertIn("expect returned false for", result["steps"][0]["detail"])


def failed(seq, run_id, message="hi"):
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "user_message", content=message),
		row(seq + 2, "run_error", message="RateLimitError: slow down"),
		row(seq + 3, "run_ended", reason="error"),
	]


def endless(seq, run_id, message="hi"):
	return [row(seq, "run_started", run_id=run_id), row(seq + 1, "user_message", content=message)]


class TestRun(SnapshotCase):
	def setUp(self):
		super().setUp()
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "eval-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
		self.folder = Path(tempfile.mkdtemp()) / "latest"
		self.folder.mkdir()

	def run_with(self, daemon, check=lambda run: None, timeout=60):
		with patch.object(DaemonClient, "for_site", return_value=daemon):
			return chat.one_run(case(check=check), 1, self.folder, None, timeout)

	def test_a_completed_turn_is_checked_and_the_chat_deleted(self):
		daemon, seen = FakeDaemon(), []
		record, provider_error = self.run_with(daemon, check=seen.append)
		self.assertEqual((record["status"], provider_error), ("pass", False), record)
		run = seen[0]
		self.assertEqual(run.reply, "done")
		self.assertEqual(
			[(c.name, c.args, c.result) for c in run.tool_calls], [("read", {"doctype": "ToDo"}, "[]")]
		)
		self.assertEqual(run.usage["cost"], 0.75)
		self.assertTrue(run.called("read", doctype="ToDo"))
		session = daemon.calls[0][1]
		self.assertIn(("delete_session", session), daemon.calls)
		self.assertFalse(frappe.db.exists("Flow Session", session))

		def fails(run):
			raise AssertionError("not what was asked")

		self.snapshot.restore()
		record, _ = self.run_with(FakeDaemon(), check=fails)
		self.assertEqual((record["status"], record["detail"]), ("fail", "not what was asked"))

	def test_a_provider_error_is_an_error_and_two_stop_the_command(self):
		record, provider_error = self.run_with(FakeDaemon(answer=failed))
		self.assertEqual(
			(record["status"], record["detail"], provider_error), ("error", "RateLimitError: slow down", True)
		)
		with (
			patch.object(DaemonClient, "for_site", return_value=FakeDaemon(answer=failed)),
			self.assertRaises(chat.Stop) as stop,
		):
			chat.run_all(
				[case(), case(), case()],
				[(self.folder, None)],
				{"skill": None, "runs": 1, "model": None, "timeout": 60, "max_cost": 1},
				self.snapshot,
			)
		self.assertEqual(len(stop.exception.records), 2)
		self.assertEqual(len(list(self.folder.glob("*.json"))), 1)  # the same case name twice

	def test_the_cost_ceiling_stops_before_the_next_run(self):
		opts = {"skill": None, "runs": 3, "model": None, "timeout": 60, "max_cost": 1}
		with (
			patch.object(DaemonClient, "for_site", return_value=FakeDaemon()),
			self.assertRaises(chat.Stop) as stop,
		):
			chat.run_all([case()], [(self.folder, None)], opts, self.snapshot)
		self.assertEqual(len(stop.exception.records), 2)  # the scripted turn costs 0.75
		self.assertIn("--max-cost", str(stop.exception))

	def test_a_run_that_never_ends_is_aborted_and_fails(self):
		daemon = FakeDaemon(answer=endless)
		daemon.running_for = 10**6
		with patch.object(chat, "ABORT_WAIT", 1):
			record, provider_error = self.run_with(daemon, timeout=1)
		self.assertEqual(record["status"], "fail")
		self.assertEqual(record["detail"], "no answer in 1 s and the chat did not stop")
		self.assertTrue(provider_error)  # a flow server that cannot stop a chat counts towards the stop
		self.assertIn("abort", [c[0] for c in daemon.calls])
