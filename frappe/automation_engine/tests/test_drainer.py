# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.drainer import claim_batch, drain, requeue_stale_running
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


def make_automation():
	doc = frappe.new_doc("Automation")
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
		frappe.db.delete("Automation")
		self.automation = make_automation()
		frappe.db.commit()

	def tearDown(self):
		frappe.db.delete(QUEUE)
		frappe.db.delete("Automation")
		frappe.db.commit()

	def add_row(self, ref_name, run_after=None):
		row = frappe.get_doc(
			{
				"doctype": QUEUE,
				"automation": self.automation,
				"ref_doctype": "ToDo",
				"ref_name": ref_name,
				"status": "Pending",
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
		self.assertEqual(self.count("Pending"), 1)

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
