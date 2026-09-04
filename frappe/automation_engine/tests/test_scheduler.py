# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from datetime import datetime, time
from unittest.mock import patch

import frappe
from frappe.automation_engine.dispatch import queue_trigger
from frappe.automation_engine.runner import TASK_METHOD, automation_task_name, execute_automation
from frappe.automation_engine.scheduler import (
	_handled_names,
	_matching_names,
	ensure_run_lookup_index,
	process_cron,
	process_date_based,
)
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


def new_scheduled_rule(**kwargs):
	"""A saved Scheduled rule, left exactly as the framework wrote it."""
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


def make_scheduled_rule(**kwargs):
	"""As above, but backdated into the fixed window the cron tests drive `now` through."""
	next_run = kwargs.pop("next_run", "2026-07-15 10:00:00")
	doc = new_scheduled_rule(**kwargs)
	doc.db_set("creation", "2026-07-15 10:00:00", update_modified=False)
	doc.creation = "2026-07-15 10:00:00"
	set_next_run(doc, next_run)
	return doc


def set_next_run(rule, value):
	frappe.db.set_value("Automation Flow", rule.name, "next_run", value, update_modified=False)


def stored_next_run(rule):
	return str(frappe.db.get_value("Automation Flow", rule.name, "next_run"))


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

	def test_rule_not_yet_due_is_skipped(self):
		rule = make_scheduled_rule(next_run="2026-07-15 10:10:00")
		process_cron(datetime(2026, 7, 15, 10, 5))
		self.assertEqual(self.rows(rule), [])

	def test_rule_not_yet_due_never_scans_its_document_type(self):
		"""The whole point of the gate: an undue rule must not touch the target table."""
		self.make_todo()
		rule = make_scheduled_rule(document_type="ToDo", next_run="2026-07-15 10:10:00")
		with patch("frappe.automation_engine.scheduler._matching_names") as scan:
			process_cron(datetime(2026, 7, 15, 10, 5))
		scan.assert_not_called()
		self.assertEqual(self.rows(rule), [])

	def test_firing_advances_next_run_past_the_tick(self):
		rule = make_scheduled_rule(cron_expression="0 10 * * *", next_run="2026-07-15 10:00:00")
		process_cron(datetime(2026, 7, 15, 10, 5))
		self.assertEqual(len(self.rows(rule)), 1)
		self.assertEqual(stored_next_run(rule), "2026-07-16 10:00:00")

	def test_next_run_advances_even_when_the_fire_was_already_handled(self):
		"""Dedup suppressing the queue row must not leave the rule pinned to a stale next_run."""
		rule = make_scheduled_rule(cron_expression="0 0 * * *", next_run="2026-07-15 00:00:00")
		self.make_run(rule)
		process_cron(datetime(2026, 7, 15, 10, 5))
		self.assertEqual(self.rows(rule), [])
		self.assertEqual(stored_next_run(rule), "2026-07-16 00:00:00")

	def test_next_run_advances_when_the_fire_predates_the_rule(self):
		rule = make_scheduled_rule(cron_expression="0 9 * * *", next_run="2026-07-15 09:00:00")
		process_cron(datetime(2026, 7, 15, 10, 5))
		self.assertEqual(self.rows(rule), [])
		self.assertEqual(stored_next_run(rule), "2026-07-16 09:00:00")

	def test_rule_without_a_next_run_is_treated_as_due(self):
		"""Flows saved before the field existed must keep firing, not stall."""
		rule = make_scheduled_rule(next_run=None)
		process_cron(datetime(2026, 7, 15, 10, 5))
		self.assertEqual(len(self.rows(rule)), 1)

	def test_saving_a_scheduled_rule_sets_its_next_run(self):
		rule = new_scheduled_rule(cron_expression="0 0 * * *")
		self.assertGreater(frappe.utils.get_datetime(stored_next_run(rule)), frappe.utils.now_datetime())

	def test_editing_the_cron_expression_recomputes_next_run(self):
		rule = new_scheduled_rule(cron_expression="0 0 1 1 *")
		rule.cron_expression = "*/5 * * * *"
		rule.save()
		due = frappe.utils.get_datetime(stored_next_run(rule))
		self.assertLess(due, frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=6))

	def test_condition_rule_evaluates_documents_without_loading_each_one(self):
		"""The condition scan must not cost a query per candidate row."""
		marker = frappe.generate_hash(length=10)
		for _ in range(5):
			self.make_todo(description=marker)
		rule = make_scheduled_rule(
			document_type="ToDo",
			filters=json.dumps([["ToDo", "description", "=", marker]]),
			condition="doc.priority == 'Medium'",
		)
		with self.assertQueryCount(2):
			names = _matching_names(rule)
		self.assertEqual(len(names), 5)

	def test_condition_rule_still_selects_only_matching_documents(self):
		marker = frappe.generate_hash(length=10)
		self.make_todo(description=marker, priority="Low")
		wanted = self.make_todo(description=marker, priority="High")
		rule = make_scheduled_rule(
			document_type="ToDo",
			filters=json.dumps([["ToDo", "description", "=", marker]]),
			condition="doc.priority == 'High'",
		)
		self.assertEqual(_matching_names(rule), [wanted.name])

	def test_condition_reading_a_child_table_falls_back_to_a_full_load(self):
		"""A bulk field fetch cannot answer `doc.event_participants`, so that rule must not use it."""
		marker = frappe.generate_hash(length=10)
		event = make_event(f"{frappe.utils.nowdate()} 10:00:00", subject=marker)
		rule = make_scheduled_rule(
			document_type="Event",
			filters=json.dumps([["Event", "subject", "=", marker]]),
			condition="doc.event_participants == []",
		)
		self.assertEqual(_matching_names(rule), [event.name])

	def test_condition_reading_a_missing_field_falls_back_rather_than_matching_everything(self):
		marker = frappe.generate_hash(length=10)
		self.make_todo(description=marker)
		rule = make_scheduled_rule(
			document_type="ToDo",
			filters=json.dumps([["ToDo", "description", "=", marker]]),
			condition="doc.not_a_real_field == 'x'",
		)
		self.assertEqual(_matching_names(rule), [])

	def test_run_lookup_index_is_created_and_idempotent(self):
		ensure_run_lookup_index()
		ensure_run_lookup_index()
		self.assertTrue(frappe.db.has_index("tabBackground Task", "automation_run_lookup"))

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
# these helpers create - otherwise "due today" sweeps up existing site data.
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


def make_event(starts_on, subject=None):
	return frappe.get_doc(
		{
			"doctype": "Event",
			"subject": subject or MARKER,
			"event_type": "Private",
			"starts_on": starts_on,
		}
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
