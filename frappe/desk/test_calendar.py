# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.calendar import get_events
from frappe.tests import IntegrationTestCase


class TestCalendar(IntegrationTestCase):
	def test_get_events_accepts_range_from_a_different_timezone(self):
		todo = frappe.get_doc(doctype="ToDo", description="Renew SSL certificate", date="2026-05-10").insert()

		events = get_events(
			doctype="ToDo",
			start="2026-04-30 23:00:00",
			end="2026-06-10 23:00:00",
			field_map=json.dumps({"start": "date", "end": "date", "title": "description"}),
		)

		self.assertIn(todo.name, [event.name for event in events])

	def test_get_events_keeps_the_last_day_of_a_datetime_range(self):
		maintenance_window = frappe.get_doc(
			doctype="Event",
			subject="Line 3 maintenance window",
			event_type="Public",
			starts_on="2026-05-10 10:00:00",
			ends_on="2026-05-10 12:00:00",
		).insert()

		events = get_events(
			doctype="Event",
			start="2026-04-30 23:00:00",
			end="2026-05-10 23:00:00",
			field_map=json.dumps({"start": "starts_on", "end": "ends_on", "title": "subject"}),
		)

		self.assertIn(maintenance_window.name, [event.name for event in events])
