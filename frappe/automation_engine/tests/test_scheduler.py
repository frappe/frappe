# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from datetime import datetime

import frappe
from frappe.automation_engine.scheduler import process_cron
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
	return doc.insert()


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

	def test_document_scheduled_rule_queues_matching_docs(self):
		low = self.make_todo(priority="Low")
		high = self.make_todo(priority="High")
		rule = make_scheduled_rule(
			document_type="ToDo",
			filters=json.dumps([["ToDo", "priority", "=", "High"]]),
		)
		process_cron(datetime(2026, 7, 15, 10, 5))
		rows = self.rows(rule)
		self.assertEqual([row.ref_name for row in rows], [high.name])
		self.assertNotEqual(rows[0].ref_name, low.name)

	def test_successful_run_prevents_duplicate_for_same_fire(self):
		rule = make_scheduled_rule()
		self.make_run(rule)
		process_cron(datetime(2026, 7, 15, 10, 5, 30))
		self.assertEqual(len(self.rows(rule)), 0)

	def make_todo(self, **kwargs):
		return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()

	def make_run(self, rule):
		run = frappe.get_doc(
			{
				"doctype": "Automation Run",
				"automation": rule.name,
				"automation_title": rule.title,
				"status": "Success",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Automation Run", run.name, "creation", "2026-07-15 10:05:10")
