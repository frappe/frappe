# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.background_jobs import get_queue


class TestSubmissionQueue(FrappeTestCase):
	queue = get_queue(qtype="default")

	def test_queue_creation(self):
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission

		doc = frappe.get_doc({"doctype": "ToDo", "description": "Something"}).insert()
		queue_submission(doc, "submit")
		submission_queue = frappe.get_last_doc("Submission Queue")
		job = self.queue.fetch_job(submission_queue.job_id)
		self.assertEqual(job.get_status(refresh=True), "queued")
