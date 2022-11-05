""" smoak tests to check that all registered background jobs execute without error.

Note: Filename is intentional to run this test roughly at end. Don't change."""

import time

import frappe
from frappe.core.doctype.rq_job.rq_job import RQJob, remove_failed_jobs
from frappe.tests.utils import FrappeTestCase, timeout


class TestScheduledJobSanity(FrappeTestCase):
	def setUp(self):
		remove_failed_jobs()

	@timeout(90)
	def test_bg_jobs_run(self):
		"""Enqueue all scheduled jobs, wait for finish and verify that none failed."""
		for scheduled_job_type in frappe.get_all("Scheduled Job Type", pluck="name"):
			frappe.get_doc("Scheduled Job Type", scheduled_job_type).enqueue(force=True)

		while RQJob.get_list({"filters": [["RQ Job", "status", "in", ("queued", "started")]]}):
			time.sleep(0.5)

		# Check no failed, if failed print full details
		failed_jobs = RQJob.get_list({"filters": [["RQ Job", "status", "=", "failed"]]})
		self.assertEqual(len(failed_jobs), 0, "Jobs failed: " + str(failed_jobs))
