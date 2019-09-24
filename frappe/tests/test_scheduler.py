from __future__ import unicode_literals

from unittest import TestCase
from dateutil.relativedelta import relativedelta
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from frappe.utils.background_jobs import enqueue, get_jobs
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

		frappe.flags.execute_job = True
		enqueue_events(site = frappe.local.site)
		frappe.flags.execute_job = False

		self.assertTrue('frappe.email.queue.clear_outbox', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.utils.change_log.check_for_update', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.email.doctype.auto_email_report.auto_email_report.send_monthly', frappe.flags.enqueued_jobs)

	def test_queue_peeking(self):
		if not frappe.db.exists('Scheduled Job Type', 'test_scheduler.test_timeout'):
			job = frappe.get_doc(dict(
				doctype = 'Scheduled Job Type',
				method = 'frappe.tests.test_scheduler.test_timeout',
				last_execution = '2010-01-01 00:00:00',
				queue = 'All'
			)).insert()
		else:
			job = frappe.get_doc('Scheduled Job Type', 'test_scheduler.test_timeout')

		self.assertTrue(job.enqueue())
		print(get_jobs(site=frappe.local.site, key='job_type'))
		self.assertFalse(job.enqueue())
		job.delete()

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
