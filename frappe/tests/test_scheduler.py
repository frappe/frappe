from __future__ import unicode_literals

from unittest import TestCase
from dateutil.relativedelta import relativedelta
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from frappe.utils.background_jobs import enqueue
from frappe.utils.scheduler import enqueue_events

import frappe
import time

def test_timeout():
	'''This function needs to be pickleable'''
	time.sleep(100)

class TestScheduler(TestCase):
	def setUp(self):
		if not frappe.get_all('Scheduled Job Type', limit=1):
			sync_jobs()

	def test_enqueue_jobs(self):
		frappe.db.sql('update `tabScheduled Job Type` set last_execution = "2010-01-01 00:00:00"')
		enqueue_events(site = frappe.local.site)

		self.assertTrue('frappe.email.queue.clear_outbox', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.utils.change_log.check_for_update', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.email.doctype.auto_email_report.auto_email_report.send_monthly', frappe.flags.enqueued_jobs)

	def test_job_timeout(self):
		return
		job = enqueue(test_timeout, timeout=10)
		count = 5
		while count > 0:
			count -= 1
			time.sleep(5)
			if job.get_status()=='failed':
				break

		self.assertTrue(job.is_failed)
