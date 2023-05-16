# Copyright (c) 2022, Frappe Technologies and Contributors

# See license.txt

import time

from rq import exceptions as rq_exc
from rq.job import Job

import frappe
from frappe.core.doctype.rq_job.rq_job import RQJob, remove_failed_jobs, stop_job
from frappe.tests.utils import FrappeTestCase, timeout
from frappe.utils import cstr, execute_in_shell
from frappe.utils.background_jobs import is_job_enqueued


class TestRQJob(FrappeTestCase):

	BG_JOB = "frappe.core.doctype.rq_job.test_rq_job.test_func"

	@timeout(seconds=20)
	def check_status(self, job: Job, status, wait=True):
		while wait:
			if not (job.is_queued or job.is_started):
				break
			time.sleep(0.2)

		self.assertEqual(frappe.get_doc("RQ Job", job.id).status, status)

	def test_serialization(self):

		job = frappe.enqueue(method=self.BG_JOB, queue="short")
		rq_job = frappe.get_doc("RQ Job", job.id)

		self.assertEqual(job, rq_job.job)
		self.assertDocumentEqual(
			{
				"name": job.id,
				"queue": "short",
				"job_name": self.BG_JOB,
				"status": "queued",
				"exc_info": None,
			},
			rq_job,
		)
		self.check_status(job, "finished")

	def test_configurable_ttl(self):
		frappe.conf.rq_job_failure_ttl = 600
		job = frappe.enqueue(method=self.BG_JOB, queue="short")

		self.assertEqual(job.failure_ttl, 600)

	def test_func_obj_serialization(self):
		job = frappe.enqueue(method=test_func, queue="short")
		rq_job = frappe.get_doc("RQ Job", job.id)
		self.assertEqual(rq_job.job_name, "test_func")

	def test_get_list_filtering(self):

		# Check failed job clearning and filtering
		remove_failed_jobs()
		jobs = RQJob.get_list({"filters": [["RQ Job", "status", "=", "failed"]]})
		self.assertEqual(jobs, [])

		# Fail a job
		job = frappe.enqueue(method=self.BG_JOB, queue="short", fail=True)
		self.check_status(job, "failed")
		jobs = RQJob.get_list({"filters": [["RQ Job", "status", "=", "failed"]]})
		self.assertEqual(len(jobs), 1)
		self.assertTrue(jobs[0].exc_info)

		# Assert that non-failed job still exists
		non_failed_jobs = RQJob.get_list({"filters": [["RQ Job", "status", "!=", "failed"]]})
		self.assertGreaterEqual(len(non_failed_jobs), 1)

		# Create a slow job and check if it's stuck in "Started"
		job = frappe.enqueue(method=self.BG_JOB, queue="short", sleep=10)
		time.sleep(3)
		self.check_status(job, "started", wait=False)
		stop_job(job_id=job.id)
		self.check_status(job, "stopped")

	def test_delete_doc(self):
		job = frappe.enqueue(method=self.BG_JOB, queue="short")
		frappe.get_doc("RQ Job", job.id).delete()

		with self.assertRaises(rq_exc.NoSuchJobError):
			job.refresh()

	@timeout(20)
	def test_multi_queue_burst_consumption(self):
		for _ in range(3):
			for q in ["default", "short"]:
				frappe.enqueue(self.BG_JOB, sleep=1, queue=q)

		_, stderr = execute_in_shell("bench worker --queue short,default --burst", check_exit_code=True)
		self.assertIn("quitting", cstr(stderr))

	@timeout(20)
	def test_job_id_dedup(self):
		job_id = "test_dedup"
		job = frappe.enqueue(self.BG_JOB, sleep=10, job_id=job_id)
		self.assertTrue(is_job_enqueued(job_id))
		stop_job(job.id)


def test_func(fail=False, sleep=0):
	if fail:
		42 / 0
	if sleep:
		time.sleep(sleep)

	return True
