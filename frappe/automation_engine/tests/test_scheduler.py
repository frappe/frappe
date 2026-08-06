# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from datetime import datetime

import frappe
from frappe.automation_engine.dispatch import queue_trigger
from frappe.automation_engine.runner import TASK_METHOD, automation_task_name
from frappe.automation_engine.scheduler import _handled_names, process_cron
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


def make_scheduled_rule(**kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = kwargs.pop("title", "Scheduled Rule")
	doc.trigger_type = "Scheduled"
	doc.cron_expression = kwargs.pop("cron_expression", "*/5 * * * *")
	doc.document_type = kwargs.pop("document_type", None)
	for key, value in kwargs.items():
		doc.set(key, value)
	doc.append(
		"actions",
		{
			"action_type": "CreateDocument",
			"params": json.dumps({"doctype": "ToDo", "values": {"description": "scheduled"}}),
		},
	)
	doc.enabled = 1
	doc.insert()
	doc.db_set("creation", "2026-07-15 10:00:00", update_modified=False)
	doc.creation = "2026-07-15 10:00:00"
	return doc


class TestScheduler(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def rows(self, automation):
		return frappe.get_all(QUEUE, filters={"automation": automation.name}, fields=["*"])

	def test_docless_scheduled_rule_queues_once_for_current_tick(self):
		rule = make_scheduled_rule()
		process_cron(datetime(2026, 7, 15, 10, 5))
		process_cron(datetime(2026, 7, 15, 10, 5, 30))
		rows = self.rows(rule)
		self.assertEqual(len(rows), 1)
		self.assertEqual(json.loads(rows[0].event_payload)["scheduled_fire_at"], "2026-07-15 10:05:00")

	def test_missed_ticks_queue_only_latest_fire(self):
		rule = make_scheduled_rule(cron_expression="* * * * *")
		process_cron(datetime(2026, 7, 15, 10, 7, 30))
		rows = self.rows(rule)
		self.assertEqual(len(rows), 1)
		self.assertEqual(json.loads(rows[0].event_payload)["scheduled_fire_at"], "2026-07-15 10:07:00")

	def test_latest_fire_supports_intervals_between_scheduler_ticks(self):
		for expression, expected in (("*/3 * * * *", "10:09:00"), ("*/7 * * * *", "10:07:00")):
			with self.subTest(expression=expression):
				rule = make_scheduled_rule(cron_expression=expression)
				process_cron(datetime(2026, 7, 15, 10, 10))
				payload = json.loads(self.rows(rule)[0].event_payload)
				self.assertTrue(payload["scheduled_fire_at"].endswith(expected))

	def test_document_scheduled_rule_queues_matching_docs(self):
		low = self.make_todo(priority="Low")
		high = self.make_todo(priority="High")
		rule = make_scheduled_rule(
			document_type="ToDo",
			filters=json.dumps([["ToDo", "priority", "=", "High"]]),
		)
		process_cron(datetime(2026, 7, 15, 10, 5))
		rows = self.rows(rule)
		queued_names = {row.ref_name for row in rows}
		self.assertIn(high.name, queued_names)
		self.assertNotIn(low.name, queued_names)

	def test_handled_documents_are_loaded_in_constant_queries(self):
		first = self.make_todo()
		second = self.make_todo()
		rule = make_scheduled_rule(document_type="ToDo")
		queue_trigger(rule.name, "ToDo", first.name)
		self.make_run(rule, second.name)

		with self.assertQueryCount(2):
			handled = _handled_names(rule.name, datetime(2026, 7, 15, 10, 5))

		self.assertEqual(handled, {first.name, second.name})

	def test_successful_run_prevents_duplicate_for_same_fire(self):
		rule = make_scheduled_rule()
		self.make_run(rule)
		process_cron(datetime(2026, 7, 15, 10, 5, 30))
		self.assertEqual(len(self.rows(rule)), 0)

	def make_todo(self, **kwargs):
		return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()

	def make_run(self, rule, reference_name=None):
		run = frappe.get_doc(
			{
				"doctype": "Background Task",
				"task_id": frappe.generate_hash(length=20),
				"task_name": automation_task_name(rule.name),
				"user": frappe.session.user,
				"method": TASK_METHOD,
				"ref_doctype": "ToDo" if reference_name else None,
				"ref_docname": reference_name,
				"status": "Completed",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Background Task", run.name, "creation", "2026-07-15 10:05:10")
