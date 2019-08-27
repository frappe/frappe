from __future__ import unicode_literals

from unittest import TestCase
from dateutil.relativedelta import relativedelta
from frappe.utils.scheduler import (enqueue_applicable_events, restrict_scheduler_events_if_dormant,
	get_enabled_scheduler_events)
from frappe import _dict
from frappe.utils.background_jobs import enqueue
from frappe.utils import now_datetime, today, add_days, add_to_date

import frappe
import time

def test_timeout():
	'''This function needs to be pickleable'''
	time.sleep(100)

class TestScheduler(TestCase):
	def setUp(self):
		frappe.db.set_global('enabled_scheduler_events', "")
		frappe.flags.ran_schedulers = []

	def test_all_events(self):
		last = now_datetime() - relativedelta(hours=2)
		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertTrue("all" in frappe.flags.ran_schedulers)

	def test_enabled_events(self):
		frappe.flags.enabled_events = ["hourly", "hourly_long", "daily", "daily_long",
			"weekly", "weekly_long", "monthly", "monthly_long"]

		# maintain last_event and next_event on the same day
		last_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		next_event = last_event + relativedelta(minutes=30)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertFalse("cron" in frappe.flags.ran_schedulers)

		# maintain last_event and next_event on the same day
		last_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		next_event = last_event + relativedelta(hours=2)

		frappe.flags.ran_schedulers = []
		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertTrue("hourly" in frappe.flags.ran_schedulers)

		frappe.flags.enabled_events = None

	def test_enabled_events_day_change(self):

		# use flags instead of globals as this test fails intermittently
		# the root cause has not been identified but the culprit seems cache
		# since cache is mutable, it maybe be changed by a parallel process
		frappe.flags.enabled_events = ["daily", "daily_long", "weekly", "weekly_long",
			"monthly", "monthly_long"]

		# maintain last_event and next_event on different days
		next_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		last_event = next_event - relativedelta(hours=2)

		frappe.flags.ran_schedulers = []
		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertFalse("hourly" in frappe.flags.ran_schedulers)

		frappe.flags.enabled_events = None





	def test_job_timeout(self):
		job = enqueue(test_timeout, timeout=10)
		count = 5
		while count > 0:
			count -= 1
			time.sleep(5)
			if job.get_status()=='failed':
				break

		self.assertTrue(job.is_failed)

	def tearDown(self):
		frappe.flags.ran_schedulers = []
