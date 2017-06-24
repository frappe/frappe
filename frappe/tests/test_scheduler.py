from __future__ import unicode_literals

from unittest import TestCase
from dateutil.relativedelta import relativedelta
from frappe.utils.scheduler import (enqueue_applicable_events, restrict_scheduler_events_if_dormant,
									 get_enabled_scheduler_events, disable_scheduler_on_expiry)
from frappe import _dict
from frappe.utils.background_jobs import enqueue
from frappe.utils import now_datetime, today, add_days, add_to_date
from frappe.limits import update_limits, clear_limit

import frappe
import json, time

def test_timeout():
	'''This function needs to be pickleable'''
	time.sleep(100)

class TestScheduler(TestCase):
	def setUp(self):
		frappe.db.set_global('enabled_scheduler_events', "")

	def test_all_events(self):
		last = now_datetime() - relativedelta(hours=2)
		enqueue_applicable_events(frappe.local.site, now_datetime(), last)
		self.assertTrue("all" in frappe.flags.ran_schedulers)

	def test_enabled_events(self):
		frappe.flags.enabled_events = ["hourly", "hourly_long", "daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"]

		# maintain last_event and next_event on the same day
		last_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		next_event = last_event + relativedelta(minutes=30)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertFalse("all" in frappe.flags.ran_schedulers)

		# maintain last_event and next_event on the same day
		last_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		next_event = last_event + relativedelta(hours=2)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertTrue("hourly" in frappe.flags.ran_schedulers)

		del frappe.flags['enabled_events']

	def test_enabled_events_day_change(self):
		val = json.dumps(["daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
		frappe.db.set_global('enabled_scheduler_events', val)

		# maintain last_event and next_event on different days
		next_event = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
		last_event = next_event - relativedelta(hours=2)

		enqueue_applicable_events(frappe.local.site, next_event, last_event)
		self.assertTrue("all" in frappe.flags.ran_schedulers)
		self.assertTrue("hourly" in frappe.flags.ran_schedulers)


	def test_restrict_scheduler_events(self):
		frappe.set_user("Administrator")
		dormant_date = add_days(today(), -5)
		frappe.db.sql('update tabUser set last_active=%s', dormant_date)

		restrict_scheduler_events_if_dormant()
		frappe.local.conf = _dict(frappe.get_site_config())

		self.assertFalse("all" in get_enabled_scheduler_events())
		self.assertTrue(frappe.conf.get('dormant', False))

		clear_limit("expiry")
		frappe.local.conf = _dict(frappe.get_site_config())


	def test_disable_scheduler_on_expiry(self):
		update_limits({'expiry': add_to_date(today(), days=-1)})
		frappe.local.conf = _dict(frappe.get_site_config())

		if not frappe.db.exists('User', 'test_scheduler@example.com'):
			user = frappe.new_doc('User')
			user.email = 'test_scheduler@example.com'
			user.first_name = 'Test_scheduler'
			user.save()
			user.add_roles('System Manager')

		frappe.db.commit()
		frappe.set_user("test_scheduler@example.com")

		disable_scheduler_on_expiry()

		ss = frappe.get_doc("System Settings")
		self.assertFalse(ss.enable_scheduler)

		clear_limit("expiry")
		frappe.local.conf = _dict(frappe.get_site_config())


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
