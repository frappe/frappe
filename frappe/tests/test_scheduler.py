from __future__ import unicode_literals

from unittest import TestCase
from frappe.utils.scheduler import enqueue_applicable_events
from frappe.utils import now_datetime
from dateutil.relativedelta import relativedelta

import frappe
import json

class TestScheduler(TestCase):

	def setUp(self):
		frappe.db.set_global('enabled_scheduler_events', "")

	def test_all_events(self):
		last = now_datetime() - relativedelta(hours=2)
		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertTrue("all" in frappe.flags.ran_schedulers)

	def test_enabled_events(self):
		val = json.dumps(["daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
		frappe.db.set_global('enabled_scheduler_events', val)

		# maintain last_event and next_event on the same day
		last_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		next_event = last_event + relativedelta(hours=2)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertFalse("all" in frappe.flags.ran_schedulers)
		self.assertFalse("hourly" in frappe.flags.ran_schedulers)
		frappe.db.set_global('enabled_scheduler_events', "")


	def test_enabled_events_day_change(self):
		val = json.dumps(["daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
		frappe.db.set_global('enabled_scheduler_events', val)

		# maintain last_event and next_event on different days
		next_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		last_event = next_event - relativedelta(hours=2)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertTrue("hourly" in frappe.flags.ran_schedulers)

	def tearDown(self):
		frappe.flags.ran_schedulers = []

