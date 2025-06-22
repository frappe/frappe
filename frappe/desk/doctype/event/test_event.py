# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Use blog post test to test user permissions logic"""

import json
from datetime import date

import frappe
from frappe.core.utils import find
from frappe.desk.doctype.event.event import get_events
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import make_test_objects


class TestEvent(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Event")
		make_test_objects("Event", reset=True)
		self.test_user = "test1@example.com"

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_allowed_public(self):
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject": "_Test Event 1"}))
		self.assertTrue(frappe.has_permission("Event", doc=doc))

	def test_not_allowed_private(self):
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject": "_Test Event 2"}))
		self.assertFalse(frappe.has_permission("Event", doc=doc))

	def test_allowed_private_if_in_event_user(self):
		name = frappe.db.get_value("Event", {"subject": "_Test Event 3"})
		frappe.share.add("Event", name, self.test_user, "read")
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", name)
		self.assertTrue(frappe.has_permission("Event", doc=doc))
		frappe.set_user("Administrator")
		frappe.share.remove("Event", name, self.test_user)

	def test_event_list(self):
		frappe.set_user(self.test_user)
		res = frappe.get_list(
			"Event", filters=[["Event", "subject", "like", "_Test Event%"]], fields=["name", "subject"]
		)
		self.assertEqual(len(res), 1)
		subjects = [r.subject for r in res]
		self.assertTrue("_Test Event 1" in subjects)
		self.assertFalse("_Test Event 3" in subjects)
		self.assertFalse("_Test Event 2" in subjects)

	def test_revert_logic(self):
		ev = frappe.get_doc(self.globalTestRecords["Event"][0]).insert()
		name = ev.name

		frappe.delete_doc("Event", ev.name)

		# insert again
		ev = frappe.get_doc(self.globalTestRecords["Event"][0]).insert()

		# the name should be same!
		self.assertEqual(ev.name, name)

	def test_assign(self):
		from frappe.desk.form.assign_to import add

		ev = frappe.get_doc(self.globalTestRecords["Event"][0]).insert()

		add(
			{
				"assign_to": ["test@example.com"],
				"doctype": "Event",
				"name": ev.name,
				"description": "Test Assignment",
			}
		)

		ev = frappe.get_doc("Event", ev.name)

		self.assertEqual(ev._assign, json.dumps(["test@example.com"]))

		# add another one
		add(
			{
				"assign_to": [self.test_user],
				"doctype": "Event",
				"name": ev.name,
				"description": "Test Assignment",
			}
		)

		ev = frappe.get_doc("Event", ev.name)

		self.assertEqual(set(json.loads(ev._assign)), {"test@example.com", self.test_user})

		# Remove an assignment
		todo = frappe.get_doc(
			"ToDo",
			{"reference_type": ev.doctype, "reference_name": ev.name, "allocated_to": self.test_user},
		)
		todo.status = "Cancelled"
		todo.save()

		ev = frappe.get_doc("Event", ev.name)
		self.assertEqual(ev._assign, json.dumps(["test@example.com"]))

		# cleanup
		ev.delete()

	def test_yearly_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2014-02-01",
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Yearly",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		applicable_dates = [
			(date(2014, 2, 1), date(2014, 2, 1)),
			(date(2015, 2, 1), date(2015, 2, 1)),
			(date(2016, 2, 1), date(2016, 2, 1)),
		]

		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

		unapplicable_dates = [
			(date(2014, 1, 20), date(2014, 1, 20)),
			(date(2015, 1, 20), date(2015, 1, 20)),
		]

		for start_date, end_date in unapplicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertFalse(
					find(event_list, test_record_matched), f"Event found between {start_date} and {end_date}"
				)

		ev.starts_on = date(2016, 2, 29)
		ev.save()

		applicable_dates = [
			(date(2016, 2, 29), date(2016, 2, 29)),
			(date(2024, 2, 28), date(2024, 2, 29)),
		]
		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

	def test_monthly_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2016-01-31",
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Monthly",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		applicable_dates = [
			(date(2016, 1, 31), date(2016, 1, 31)),
			(date(2016, 2, 29), date(2016, 2, 29)),
			(date(2016, 3, 31), date(2016, 3, 31)),
			(date(2016, 4, 30), date(2016, 4, 30)),
		]
		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

	def test_quaterly_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2023-02-17",
				"repeat_till": "2024-02-17",
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Quarterly",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		# Test Quaterly months
		applicable_dates = [
			(date(2023, 2, 17), date(2023, 2, 17)),
			(date(2023, 5, 17), date(2023, 5, 17)),
			(date(2023, 8, 17), date(2023, 8, 17)),
			(date(2023, 11, 17), date(2023, 11, 17)),
		]

		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

		unapplicable_dates = [
			# Test before event start date and after event end date
			(date(2022, 11, 17), date(2022, 11, 17)),
			(date(2024, 2, 17), date(2024, 2, 17)),
			# Test months that aren't part of the quarterly cycle
			(date(2023, 12, 17), date(2023, 12, 17)),
			(date(2023, 3, 17), date(2023, 3, 17)),
		]

		for start_date, end_date in unapplicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertFalse(
					find(event_list, test_record_matched), f"Event found between {start_date} and {end_date}"
				)

	def test_half_yearly_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2023-02-17",
				"repeat_till": "2024-02-17",
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Half Yearly",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		# Test Half Yearly months
		applicable_dates = [
			(date(2023, 2, 17), date(2023, 2, 17)),
			(date(2023, 8, 17), date(2023, 8, 17)),
		]

		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

		unapplicable_dates = [
			# Test before event start date and after event end date
			(date(2022, 8, 17), date(2022, 8, 17)),
			(date(2024, 2, 17), date(2024, 2, 17)),
			# Test months that aren't part of the half yearly cycle
			(date(2023, 12, 17), date(2023, 12, 17)),
			(date(2023, 5, 17), date(2023, 5, 17)),
		]

		for start_date, end_date in unapplicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertFalse(
					find(event_list, test_record_matched), f"Event found between {start_date} and {end_date}"
				)

	def test_daily_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2023-02-17",
				"repeat_till": "2024-02-17",
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Daily",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		applicable_dates = [
			(date(2023, 2, 17), date(2023, 2, 17)),
			(date(2024, 1, 1), date(2024, 1, 1)),
		]
		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

		unapplicable_dates = [
			(
				date(2024, 2, 17),
				date(2024, 2, 17),
			),  # this is unapplicable since repeat_till is 2024-02-17 00:00:00
			(date(2022, 8, 17), date(2022, 8, 17)),
			(date(2024, 2, 18), date(2024, 2, 18)),
		]
		for start_date, end_date in unapplicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertFalse(
					find(event_list, test_record_matched), f"Event found between {start_date} and {end_date}"
				)

	def test_weekly_repeat(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Event",
				"starts_on": "2025-04-15 16:00:00",
				"repeat_till": "2025-05-06 23:59:59",
				"tuesday": 1,
				"wednesday": 1,
				"friday": 1,
				"event_type": "Public",
				"repeat_this_event": 1,
				"repeat_on": "Weekly",
			}
		).insert()

		def test_record_matched(e):
			return e.name == ev.name

		applicable_dates = [
			(date(2025, 4, 15), date(2025, 4, 15)),
			(date(2025, 4, 22), date(2025, 4, 22)),
			(date(2025, 4, 29), date(2025, 4, 29)),
			(date(2025, 4, 30), date(2025, 4, 30)),
			(date(2025, 5, 2), date(2025, 5, 2)),
		]
		for start_date, end_date in applicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertTrue(
					find(event_list, test_record_matched),
					f"Event not found between {start_date} and {end_date}",
				)

		unapplicable_dates = [
			# Test before event start date and after event end date
			(date(2022, 8, 17), date(2022, 8, 17)),
			(date(2024, 2, 18), date(2024, 2, 18)),
			# Test dates that aren't part of the weekly cycle
			(date(2023, 5, 17), date(2023, 5, 17)),
			(date(2023, 5, 18), date(2023, 5, 18)),
		]
		for start_date, end_date in unapplicable_dates:
			event_list = get_events(start_date, end_date, "Administrator", for_reminder=True)
			with self.subTest(start_date=start_date, end_date=end_date):
				self.assertFalse(
					find(event_list, test_record_matched), f"Event found between {start_date} and {end_date}"
				)

		# Test occurences of events in a timespan
		event_list = get_events(date(2025, 4, 29), date(2025, 5, 2), "Administrator", for_reminder=True)
		self.assertEqual(len(event_list), 3)
