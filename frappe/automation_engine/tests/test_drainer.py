# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
import frappe.automation_engine.drainer as drainer
from frappe.automation_engine import queue_status
from frappe.automation_engine.drainer import (
	claim_batch,
	drain,
	drain_due,
	promote_due_scheduled,
	requeue_stale_running,
)
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


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
		frappe.db.commit()

	def tearDown(self):
		frappe.db.delete(QUEUE)
		frappe.db.delete("Automation Flow")
		frappe.db.commit()

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
		frappe.db.commit()
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
		frappe.db.commit()
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
		frappe.db.commit()
		requeue_stale_running()
		frappe.db.commit()
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
		for i in range(3):
			self.add_row(f"T{i}")

		processed = []

		def executor(name):
			processed.append(name)
			if len(processed) == 2:
				raise ValueError("boom")
			frappe.db.set_value(QUEUE, name, "status", "Done")

		drain(batch_size=3, executor=executor)

		self.assertEqual(len(processed), 3)
		self.assertEqual(self.count("Done"), 2)
		# The failed row keeps its claim; requeue_stale_running() releases it.
		self.assertEqual(self.count("Running"), 1)

	def test_a_failing_row_does_not_roll_back_the_rows_before_it(self):
		names = [self.add_row(f"T{i}") for i in range(2)]

		def executor(name):
			frappe.db.set_value(QUEUE, name, "status", "Done")
			if name == names[1]:
				raise ValueError("boom")

		drain(batch_size=2, executor=executor)

		# Without a commit per row, the second row's rollback would take the first one's
		# write with it and both would sit Running until the stale sweep.
		self.assertEqual(frappe.db.get_value(QUEUE, names[0], "status"), "Done")
		self.assertEqual(frappe.db.get_value(QUEUE, names[1], "status"), "Running")

	def test_kill_switch_stops_drain(self):
		for i in range(3):
			self.add_row(f"T{i}")

		processed = []
		frappe.conf.automation_disabled = True
		try:
			drain(executor=lambda name: processed.append(name))
		finally:
			frappe.conf.automation_disabled = False

		self.assertEqual(processed, [])
		self.assertEqual(self.count("Pending"), 3)

	def test_drain_due_drains_inline_without_kicking_a_job(self):
		import frappe.automation_engine.runner as runner

		for i in range(3):
			self.add_row(f"T{i}")

		processed = []
		kicks = []
		original_executor = runner.execute_automation
		original_rekick = drainer._rekick

		def executor(name):
			processed.append(name)
			frappe.db.set_value(QUEUE, name, "status", "Done")

		runner.execute_automation = executor
		drainer._rekick = lambda: kicks.append(1)
		try:
			drain_due()
		finally:
			runner.execute_automation = original_executor
			drainer._rekick = original_rekick

		self.assertEqual(len(processed), 3)
		self.assertEqual(kicks, [])
		self.assertEqual(self.count("Pending"), 0)

	def test_old_mariadb_uses_plain_for_update(self):
		original = drainer._mariadb_supports_skip_locked
		original_db_type = frappe.db.db_type
		drainer._mariadb_supports_skip_locked = lambda: False
		frappe.db.db_type = "mariadb"
		try:
			self.assertEqual(drainer._lock_clause(), "FOR UPDATE")
		finally:
			drainer._mariadb_supports_skip_locked = original
			frappe.db.db_type = original_db_type
