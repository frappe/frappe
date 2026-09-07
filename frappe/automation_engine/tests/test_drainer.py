# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
import frappe.automation_engine.drainer as drainer
from frappe.automation_engine import settings
from frappe.automation_engine.drainer import (
	claim_batch,
	drain,
	drain_due,
	promote_due_scheduled,
	requeue_stale_running,
)
from frappe.automation_engine.queue import (
	QUEUE,
	clear_effects,
	effects_delivered,
	mark_effects_delivered,
	queue_status,
)
from frappe.tests import IntegrationTestCase


def make_automation():
	doc = frappe.new_doc("Automation Flow")
	doc.title = "Drainer Rule"
	doc.trigger_type = "Doc Created"
	doc.document_type = "ToDo"
	doc.append("actions", {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'})
	doc.enabled = 1
	doc.insert()
	return doc.name


class TestDrainer(IntegrationTestCase):
	# claim_batch commits (to release row locks), so these tests clean up explicitly
	# instead of relying on the harness transaction rollback.

	def setUp(self):
		frappe.db.delete(QUEUE)
		frappe.db.delete("Automation Flow")
		self.automation = make_automation()
		# claim_batch commits, so these tests cannot rely on the harness rollback.
		frappe.db.commit()  # nosemgrep

	def tearDown(self):
		for name in frappe.get_all(QUEUE, pluck="name"):
			clear_effects(name)
		frappe.db.delete(QUEUE)
		frappe.db.delete("Automation Flow")
		frappe.db.commit()  # nosemgrep

	def add_row(self, ref_name, run_after=None, status=None):
		row = frappe.get_doc(
			{
				"doctype": QUEUE,
				"automation": self.automation,
				"ref_doctype": "ToDo",
				"ref_name": ref_name,
				"status": status or queue_status(run_after),
				"triggered_at": frappe.utils.now(),
				"run_after": run_after,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		return row.name

	def count(self, status):
		return frappe.db.count(QUEUE, {"status": status})

	def test_batch_claim_limits_and_marks_running(self):
		for i in range(5):
			self.add_row(f"T{i}")
		claimed = claim_batch(2)
		self.assertEqual(len(claimed), 2)
		self.assertEqual(self.count("Running"), 2)
		self.assertEqual(self.count("Pending"), 3)

	def test_future_run_after_not_claimed(self):
		self.add_row("due")
		self.add_row("later", run_after=frappe.utils.add_to_date(None, days=1))
		claimed = claim_batch(10)
		self.assertEqual(len(claimed), 1)
		self.assertEqual(self.count("Pending"), 0)
		self.assertEqual(self.count("Scheduled"), 1)

	def test_due_scheduled_row_is_promoted_to_pending(self):
		past = frappe.utils.add_to_date(frappe.utils.now(), minutes=-5)
		name = self.add_row("was_waiting", run_after=past, status="Scheduled")
		promote_due_scheduled()
		frappe.db.commit()  # nosemgrep
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Pending")

	def test_due_scheduled_row_is_claimed_without_promotion(self):
		past = frappe.utils.add_to_date(frappe.utils.now(), minutes=-5)
		self.add_row("overdue", run_after=past, status="Scheduled")
		self.assertEqual(len(claim_batch(10)), 1)

	def test_scheduled_row_stays_put_until_due(self):
		self.add_row("waiting", run_after=frappe.utils.add_to_date(None, days=2))
		drain(executor=lambda name: None)
		self.assertEqual(self.count("Scheduled"), 1)
		self.assertEqual(self.count("Running"), 0)

	def test_second_claim_excludes_already_running(self):
		for i in range(4):
			self.add_row(f"T{i}")
		first = claim_batch(2)
		second = claim_batch(10)
		self.assertEqual(len(second), 2)
		self.assertEqual(set(first) & set(second), set())

	def test_stale_running_row_is_requeued(self):
		name = self.add_row("stale")
		old = frappe.utils.add_to_date(frappe.utils.now(), minutes=-120)
		frappe.db.sql(
			f"UPDATE `tab{QUEUE}` SET status = 'Running', modified = %s WHERE name = %s", (old, name)
		)
		frappe.db.commit()  # nosemgrep
		requeue_stale_running()
		frappe.db.commit()  # nosemgrep
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Pending")

	def test_drain_processes_all_with_injected_executor(self):
		for i in range(3):
			self.add_row(f"T{i}")

		processed = []

		def executor(name):
			processed.append(name)
			frappe.db.set_value(QUEUE, name, "status", "Done")

		drain(batch_size=2, executor=executor)
		self.assertEqual(len(processed), 3)
		self.assertEqual(self.count("Pending"), 0)
		self.assertEqual(self.count("Running"), 0)

	def test_one_failing_row_does_not_stop_the_batch(self):
		names = [self.add_row(f"T{i}") for i in range(3)]

		processed = []

		def executor(name):
			processed.append(name)
			if name == names[1]:
				raise ValueError("boom")
			frappe.db.set_value(QUEUE, name, "status", "Done")

		drain(batch_size=3, executor=executor)

		self.assertEqual(self.count("Done"), 2)
		# The failing row is retried to exhaustion and then failed, rather than holding its
		# claim until the stale sweep. Nothing is left Running.
		self.assertEqual(frappe.db.get_value(QUEUE, names[1], "status"), "Failed")
		self.assertEqual(self.count("Running"), 0)

	def test_a_failing_row_does_not_roll_back_the_rows_before_it(self):
		names = [self.add_row(f"T{i}") for i in range(2)]

		def executor(name):
			frappe.db.set_value(QUEUE, name, "status", "Done")
			if name == names[1]:
				raise ValueError("boom")

		drain(batch_size=2, executor=executor)

		# Without a savepoint per row, the second row's rollback would take the first one's
		# write with it and both would sit Running until the stale sweep.
		self.assertEqual(frappe.db.get_value(QUEUE, names[0], "status"), "Done")
		self.assertEqual(frappe.db.get_value(QUEUE, names[1], "status"), "Failed")

	def test_escaped_row_is_released_instead_of_left_running(self):
		"""A run that escapes the runner must not hold its claim until the stale sweep."""
		name = self.add_row("escapes")
		claimed = claim_batch(1)

		drainer.execute_batch(lambda _name: 1 / 0, claimed)
		frappe.db.commit()  # nosemgrep

		row = frappe.db.get_value(QUEUE, name, ["status", "attempt"], as_dict=True)
		self.assertEqual(row.status, "Pending")
		self.assertEqual(row.attempt, 1)

	def test_escaped_row_fails_once_attempts_are_exhausted(self):
		"""A row that throws on every claim must stop being reclaimed - drain has to terminate."""
		name = self.add_row("always_fails")

		drain(executor=lambda _name: 1 / 0)

		row = frappe.db.get_value(QUEUE, name, ["status", "attempt"], as_dict=True)
		self.assertEqual(row.status, "Failed")
		self.assertEqual(row.attempt, settings.get("max_attempts"))

	def test_a_row_that_reached_outside_is_failed_rather_than_queued_again(self):
		"""A webhook cannot be un-sent. If the run throws after one goes out, replaying the row
		from the top would send it twice, so the row is failed instead."""
		name = self.add_row("delivered")
		claimed = claim_batch(1)

		def executor(row_name):
			mark_effects_delivered(row_name)
			raise ValueError("finalize blew up after the webhook went out")

		drainer.execute_batch(executor, claimed)
		frappe.db.commit()  # nosemgrep

		row = frappe.db.get_value(QUEUE, name, ["status", "attempt"], as_dict=True)
		self.assertEqual(row.status, "Failed")
		self.assertEqual(row.attempt, 0)
		self.assertFalse(effects_delivered(name))

	def test_a_row_that_only_touched_the_database_is_still_retried(self):
		"""The mark is what makes a failure final; without it, failures retry as before."""
		name = self.add_row("db_only")
		claimed = claim_batch(1)

		drainer.execute_batch(lambda _name: 1 / 0, claimed)
		frappe.db.commit()  # nosemgrep

		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Pending")

	def test_a_failed_cache_cleanup_does_not_re_run_a_committed_group(self):
		"""Clearing the mark is bookkeeping after the fact. If it throws, the group has already
		been committed, and running it again would repeat every external action in it."""
		name = self.add_row("committed_then_cleanup_failed")
		claimed = claim_batch(1)
		runs = []

		with patch("frappe.automation_engine.drainer.clear_effects", side_effect=ValueError("redis is down")):
			self.assertRaises(ValueError, drainer.execute_batch, runs.append, claimed)

		self.assertEqual(runs, [name])

	def test_the_mark_is_dropped_once_the_outcome_is_committed(self):
		name = self.add_row("delivered_then_committed")
		claimed = claim_batch(1)

		drainer.execute_batch(mark_effects_delivered, claimed)

		self.assertFalse(effects_delivered(name))

	def test_a_delivered_row_is_not_re_run_when_its_group_commit_fails(self):
		"""End to end: the row sends its webhook, the group commit fails and takes the database
		half back, and the serial re-run must not send it again."""
		name = self.add_row("delivered_then_commit_failed")
		claimed = claim_batch(1)
		runs = []

		def executor(row_name):
			runs.append(row_name)
			mark_effects_delivered(row_name)
			frappe.db.set_value(QUEUE, row_name, "status", "Done")

		original_commit = frappe.db.commit
		calls = []

		def failing_commit(*args, **kwargs):
			calls.append(1)
			if len(calls) == 1:
				raise frappe.db.SQLError("group commit failed")
			return original_commit(*args, **kwargs)

		with patch.object(frappe.db, "commit", failing_commit):
			drainer.execute_batch(executor, claimed)

		self.assertEqual(runs, [name])
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Failed")

	def test_a_delivered_row_is_not_re_run_when_the_group_commit_fails(self):
		"""The group rollback takes back the database half of a run whose webhook already left.
		Re-running the group serially must skip that row rather than send it again."""
		name = self.add_row("delivered_in_group")
		claim_batch(1)
		mark_effects_delivered(name)
		runs = []

		drainer.execute_claimed(runs.append, name)

		self.assertEqual(runs, [])
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Failed")

	def test_group_commit_failure_reruns_the_group_one_row_at_a_time(self):
		names = [self.add_row(f"T{i}") for i in range(3)]
		claimed = claim_batch(len(names))
		attempts = []

		def executor(name):
			attempts.append(name)
			frappe.db.set_value(QUEUE, name, "status", "Done")

		original_commit = frappe.db.commit
		calls = []

		def flaky_commit(*args, **kwargs):
			calls.append(1)
			if len(calls) == 1:
				raise Exception("connection lost")
			return original_commit(*args, **kwargs)

		frappe.db.commit = flaky_commit
		try:
			drainer.execute_batch(executor, claimed)
		finally:
			frappe.db.commit = original_commit

		# Every row ran once in the group and again on the serial retry, and the retry is
		# what actually landed: the group's writes went out with the failed commit.
		self.assertEqual(len(attempts), 2 * len(names))
		self.assertEqual(self.count("Done"), len(names))

	def test_commit_every_bounds_the_group(self):
		for i in range(4):
			self.add_row(f"T{i}")
		claimed = claim_batch(4)

		original_commit = frappe.db.commit
		commits = []

		def counting_commit(*args, **kwargs):
			commits.append(1)
			return original_commit(*args, **kwargs)

		frappe.db.commit = counting_commit
		try:
			with self.change_settings("Automation Settings", commit_every=2):
				drainer.execute_batch(lambda name: None, claimed)
		finally:
			frappe.db.commit = original_commit

		# Four rows at two per group is two commits, not four.
		self.assertEqual(len(commits), 2)

	def test_time_budget_stops_claiming_and_rekicks(self):
		for i in range(4):
			self.add_row(f"T{i}")

		processed = []
		# A budget this small expires during the first batch, so the second is never claimed.
		with (
			patch.object(drainer, "kick_drainer") as kick,
			self.change_settings("Automation Settings", drain_seconds=0.001),
		):
			drain(batch_size=2, executor=processed.append)

		self.assertEqual(len(processed), 2)
		# Two rows are still due, so the drain hands off to a fresh job instead of running on.
		self.assertEqual(kick.call_count, 1)
		self.assertEqual(self.count("Pending"), 2)

	def test_budget_is_a_fraction_of_the_queue_timeout(self):
		with self.change_settings("Automation Settings", drain_seconds=0):
			self.assertLess(drainer.drain_time_budget(), 300)
			self.assertGreater(drainer.drain_time_budget(), 0)

	def test_kill_switch_stops_drain(self):
		for i in range(3):
			self.add_row(f"T{i}")

		processed = []
		with self.change_settings("Automation Settings", disable_automations=1):
			drain(executor=lambda name: processed.append(name))

		self.assertEqual(processed, [])
		self.assertEqual(self.count("Pending"), 3)

	def test_site_config_kill_switch_overrides_settings(self):
		for i in range(3):
			self.add_row(f"T{i}")

		processed = []
		frappe.conf.automation_disabled = True
		try:
			drain(executor=lambda name: processed.append(name))
		finally:
			frappe.conf.pop("automation_disabled", None)

		self.assertEqual(processed, [])
		self.assertEqual(self.count("Pending"), 3)

	def test_drain_due_drains_inline_without_kicking_a_job(self):
		import frappe.automation_engine.runner as runner

		for i in range(3):
			self.add_row(f"T{i}")

		processed = []

		def executor(name):
			processed.append(name)
			frappe.db.set_value(QUEUE, name, "status", "Done")

		with (
			patch.object(runner, "execute_automation", executor),
			patch.object(drainer, "kick_drainer") as kick,
		):
			drain_due()

		self.assertEqual(len(processed), 3)
		self.assertEqual(kick.call_count, 0)
		self.assertEqual(self.count("Pending"), 0)

	def test_old_mariadb_uses_plain_for_update(self):
		original_db_type = frappe.db.db_type
		frappe.db.db_type = "mariadb"
		try:
			with patch.object(frappe.db, "sql", return_value=[("10.5.21-MariaDB",)]):
				self.assertFalse(drainer.supports_skip_locked())
				self.assertEqual(drainer._lock_clause(), "FOR UPDATE")
		finally:
			frappe.db.db_type = original_db_type
