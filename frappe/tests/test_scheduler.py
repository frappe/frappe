from __future__ import unicode_literals

from unittest import TestCase
from frappe.utils.scheduler import enqueue_applicable_events
from frappe.utils import now_datetime, get_datetime
from dateutil.relativedelta import relativedelta

import frappe
import json

class TestScheduler(TestCase):

	def setUp(self):
		frappe.flags.ran_schedulers = []
		frappe.db.set_global('enabled_scheduler_events', "")

	def test_all_events(self):
		last = get_datetime(frappe.db.get_global('scheduler_last_event'))
		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertTrue("all" in frappe.flags.ran_schedulers)

	def test_enabled_events(self):
		val = json.dumps(["daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
		frappe.db.set_global('enabled_scheduler_events', val)

		last = now_datetime() - relativedelta(hours=2)

		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertFalse("all" in frappe.flags.ran_schedulers)
		self.assertFalse("hourly" in frappe.flags.ran_schedulers)
		frappe.db.set_global('enabled_scheduler_events', "")


	def test_enabled_events_day_change(self):
		val = json.dumps(["daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
		frappe.db.set_global('enabled_scheduler_events', val)

		last = now_datetime() - relativedelta(days=2)

		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertTrue("hourly" in frappe.flags.ran_schedulers)
