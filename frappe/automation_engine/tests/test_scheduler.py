# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from datetime import datetime, time

import frappe
from frappe.automation_engine.dispatch import queue_trigger
from frappe.automation_engine.runner import TASK_METHOD, automation_task_name, execute_automation
from frappe.automation_engine.scheduler import _handled_names, process_cron, process_date_based
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


# The test site carries real ToDos and Events, so every date rule is scoped to the rows
# these helpers create — otherwise "due today" sweeps up existing site data.
MARKER = "automation-date-test"


def make_date_rule(**kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = kwargs.pop("title", "Date Rule")
	doc.trigger_type = "Date Based"
	doc.document_type = kwargs.pop("document_type", "ToDo")
	doc.date_field = kwargs.pop("date_field", "date")
	doc.date_offset = kwargs.pop("date_offset", 3)
	doc.date_direction = kwargs.pop("date_direction", "Before")
	doc.filters = kwargs.pop("filters", json.dumps([[doc.document_type, _marker_field(doc), "=", MARKER]]))
	for key, value in kwargs.items():
		doc.set(key, value)
	doc.append(
		"actions",
		{
			"action_type": "CreateDocument",
			"params": json.dumps({"doctype": "ToDo", "values": {"description": "renewal-nudge"}}),
		},
	)
	doc.enabled = 1
	doc.insert()
	return doc


def _marker_field(doc):
	return "subject" if doc.document_type == "Event" else "description"


def make_todo(date, **kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": MARKER, "date": date, **kwargs}).insert()


def make_event(starts_on):
	return frappe.get_doc(
		{"doctype": "Event", "subject": MARKER, "event_type": "Private", "starts_on": starts_on}
	).insert()


class TestDateBasedScheduler(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.today = frappe.utils.getdate(frappe.utils.now_datetime())

	def tearDown(self):
		frappe.db.rollback()

	def rows(self, automation):
		return frappe.get_all(QUEUE, filters={"automation": automation.name}, fields=["*"])

	def days_out(self, days):
		return frappe.utils.add_days(self.today, days)

	def test_fires_for_a_document_due_at_the_offset(self):
		todo = make_todo(self.days_out(3))
		rule = make_date_rule(date_offset=3, date_direction="Before")
		process_date_based()
		rows = self.rows(rule)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].ref_name, todo.name)
		self.assertEqual(json.loads(rows[0].event_payload)["trigger_type"], "Date Based")

	def test_ignores_documents_outside_the_offset(self):
		make_todo(self.days_out(5))
		rule = make_date_rule(date_offset=3, date_direction="Before")
		process_date_based()
		self.assertEqual(self.rows(rule), [])

	def test_after_direction_looks_backwards(self):
		todo = make_todo(self.days_out(-2))
		rule = make_date_rule(date_offset=2, date_direction="After")
		process_date_based()
		rows = self.rows(rule)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].ref_name, todo.name)

	def test_zero_offset_fires_on_the_day_itself(self):
		todo = make_todo(self.today)
		rule = make_date_rule(date_offset=0, date_direction="Before")
		process_date_based()
		self.assertEqual([r.ref_name for r in self.rows(rule)], [todo.name])

	def test_fires_exactly_once_across_24_hourly_ticks(self):
		make_todo(self.days_out(3))
		rule = make_date_rule(date_offset=3, date_direction="Before")
		for hour in range(24):
			process_date_based(datetime.combine(self.today, time(hour, 30)))
		self.assertEqual(len(self.rows(rule)), 1)

	def test_completed_run_blocks_a_second_fire_the_same_day(self):
		make_todo(self.days_out(3))
		rule = make_date_rule(date_offset=3, date_direction="Before")
		process_date_based()
		execute_automation(self.rows(rule)[0].name)

		# The run deleted its queue row; the remaining ticks must not queue a fresh one.
		process_date_based(datetime.combine(self.today, time(23, 30)))
		self.assertEqual(self.rows(rule), [])
		self.assertEqual(frappe.db.count("ToDo", {"description": "renewal-nudge"}), 1)

	def test_respects_rule_filters(self):
		make_todo(self.days_out(3), priority="Low")
		wanted = make_todo(self.days_out(3), priority="High")
		rule = make_date_rule(
			date_offset=3,
			filters=json.dumps([["ToDo", "description", "=", MARKER], ["ToDo", "priority", "=", "High"]]),
		)
		process_date_based()
		self.assertEqual([r.ref_name for r in self.rows(rule)], [wanted.name])

	def test_respects_rule_condition(self):
		make_todo(self.days_out(3), priority="Low")
		wanted = make_todo(self.days_out(3), priority="High")
		rule = make_date_rule(date_offset=3, condition="doc.priority == 'High'")
		process_date_based()
		self.assertEqual([r.ref_name for r in self.rows(rule)], [wanted.name])

	def test_datetime_field_matches_anywhere_in_the_day(self):
		"""The window spans the whole target day, so a late-evening timestamp still fires."""
		event = make_event(f"{self.days_out(3)} 23:45:00")
		rule = make_date_rule(document_type="Event", date_field="starts_on", date_offset=3)
		process_date_based()
		self.assertEqual([r.ref_name for r in self.rows(rule)], [event.name])

	def test_target_day_follows_the_site_timezone(self):
		"""'now' is site-local, so the offset is measured off the site's calendar day."""
		original = frappe.db.get_single_value("System Settings", "time_zone")
		frappe.db.set_single_value("System Settings", "time_zone", "Pacific/Kiritimati")
		frappe.local.cache.pop("time_zone", None)
		try:
			local_today = frappe.utils.getdate(frappe.utils.now_datetime())
			todo = make_todo(frappe.utils.add_days(local_today, 3))
			rule = make_date_rule(date_offset=3, date_direction="Before")
			process_date_based()
			self.assertEqual([r.ref_name for r in self.rows(rule)], [todo.name])
		finally:
			frappe.db.set_single_value("System Settings", "time_zone", original)
			frappe.local.cache.pop("time_zone", None)

	def test_disabled_rule_never_fires(self):
		make_todo(self.days_out(3))
		rule = make_date_rule(date_offset=3)
		frappe.db.set_value("Automation Flow", rule.name, "enabled", 0, update_modified=False)
		process_date_based()
		self.assertEqual(self.rows(rule), [])
