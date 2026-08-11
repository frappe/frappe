# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.dispatch import queue_trigger
from frappe.automation_engine.registry import clear_automation_cache
from frappe.tests import IntegrationTestCase


def make_automation():
	doc = frappe.new_doc("Automation Flow")
	doc.title = "Outbox Rule"
	doc.trigger_type = "Doc Created"
	doc.document_type = "ToDo"
	doc.append("actions", {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'})
	doc.enabled = 1
	doc.insert()
	return doc.name


def rows(automation, **filters):
	return frappe.get_all("Automation Trigger Queue", filters={"automation": automation, **filters})


class TestOutbox(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Automation Trigger Queue")
		frappe.db.delete("Automation Flow")
		clear_automation_cache()
		self.automation = make_automation()

	def tearDown(self):
		frappe.db.rollback()
		clear_automation_cache()

	def test_dedup_upsert_keeps_one_pending_row(self):
		first = queue_trigger(self.automation, "ToDo", "TODO-1")
		second = queue_trigger(self.automation, "ToDo", "TODO-1")
		self.assertEqual(first, second)
		self.assertEqual(len(rows(self.automation, status="Pending")), 1)

	def test_running_row_does_not_block_new_pending(self):
		name = queue_trigger(self.automation, "ToDo", "TODO-1")
		frappe.db.set_value("Automation Trigger Queue", name, "status", "Running")
		queue_trigger(self.automation, "ToDo", "TODO-1")
		self.assertEqual(len(rows(self.automation, status="Running")), 1)
		self.assertEqual(len(rows(self.automation, status="Pending")), 1)

	def test_queue_trigger_is_transactional(self):
		frappe.db.savepoint("outbox_sp")
		queue_trigger(self.automation, "ToDo", "TODO-9")
		self.assertEqual(len(rows(self.automation, ref_name="TODO-9")), 1)
		frappe.db.rollback(save_point="outbox_sp")
		self.assertEqual(len(rows(self.automation, ref_name="TODO-9")), 0)

	def _raw_pending(self, ref_name, status="Pending"):
		return frappe.get_doc(
			{
				"doctype": "Automation Trigger Queue",
				"automation": self.automation,
				"ref_doctype": "ToDo",
				"ref_name": ref_name,
				"status": status,
				"triggered_at": frappe.utils.now(),
			}
		).insert(ignore_permissions=True)

	def test_dedup_key_index_blocks_duplicate_pending(self):
		self._raw_pending("TODO-DUP")
		with self.assertRaises((frappe.UniqueValidationError, frappe.DuplicateEntryError)):
			self._raw_pending("TODO-DUP")

	def test_done_and_pending_rows_coexist(self):
		# dedup_key is NULL for non-waiting rows, so a Done row never blocks a fresh Pending one.
		self._raw_pending("TODO-COEXIST", status="Done")
		self._raw_pending("TODO-COEXIST")
		self.assertEqual(len(rows(self.automation, ref_name="TODO-COEXIST")), 2)

	def test_future_run_after_queues_as_scheduled(self):
		later = frappe.utils.add_to_date(frappe.utils.now(), days=2)
		name = queue_trigger(self.automation, "ToDo", "TODO-LATER", run_after=later)
		self.assertEqual(frappe.db.get_value("Automation Trigger Queue", name, "status"), "Scheduled")

	def test_scheduled_row_is_deduplicated_like_pending(self):
		later = frappe.utils.add_to_date(frappe.utils.now(), days=2)
		first = queue_trigger(self.automation, "ToDo", "TODO-LATER", run_after=later)
		second = queue_trigger(self.automation, "ToDo", "TODO-LATER", run_after=later)
		self.assertEqual(first, second)
		self.assertEqual(len(rows(self.automation, ref_name="TODO-LATER")), 1)

	def test_scheduled_row_index_blocks_duplicate(self):
		self._raw_pending("TODO-SCHED", status="Scheduled")
		with self.assertRaises((frappe.UniqueValidationError, frappe.DuplicateEntryError)):
			self._raw_pending("TODO-SCHED", status="Scheduled")

	def test_retrigger_of_scheduled_row_pulls_it_forward(self):
		later = frappe.utils.add_to_date(frappe.utils.now(), days=2)
		name = queue_trigger(self.automation, "ToDo", "TODO-FORWARD", run_after=later)
		queue_trigger(self.automation, "ToDo", "TODO-FORWARD")
		row = frappe.db.get_value("Automation Trigger Queue", name, ["status", "run_after"], as_dict=True)
		self.assertEqual(row.status, "Pending")
		self.assertIsNone(row.run_after)
