# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import time
import typing

import frappe
from frappe.tests import IntegrationTestCase, timeout
from frappe.utils.background_jobs import get_queue

if typing.TYPE_CHECKING:
	from rq.job import Job


class TestSubmissionQueue(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.queue = get_queue(qtype="default")

	@timeout(seconds=20)
	def check_status(self, job: "Job", status, wait=True):
		if wait:
			while True:
				if job.is_queued or job.is_started:
					time.sleep(0.2)
				else:
					break
		self.assertEqual(frappe.get_doc("RQ Job", job.id).status, status)

	def test_queue_operation(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission

		if not frappe.db.table_exists("Test Submission Queue", cached=False):
			doc = new_doctype("Test Submission Queue", is_submittable=True, queue_in_background=True)
			doc.insert()

		d = frappe.new_doc("Test Submission Queue")
		d.update({"some_fieldname": "Random"})
		d.insert()

		frappe.db.commit()
		queue_submission(d, "submit")
		frappe.db.commit()

		# Waiting for execution
		time.sleep(4)
		submission_queue = frappe.get_last_doc("Submission Queue")

		# Test queueing / starting
		job = self.queue.fetch_job(submission_queue.job_id)
		# Test completion
		self.check_status(job, status="finished")

	def test_cancel_operation(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission

		if not frappe.db.table_exists("Test Submission Queue", cached=False):
			doc = new_doctype("Test Submission Queue", is_submittable=True, queue_in_background=True)
			doc.insert()

		d = frappe.new_doc("Test Submission Queue")
		d.update({"some_fieldname": "Random"})
		d.insert()
		d.submit()
		frappe.db.commit()

		self.assertEqual(d.docstatus, 1)

		queue_submission(d, "Cancel")
		frappe.db.commit()

		time.sleep(4)
		submission_queue = frappe.get_last_doc("Submission Queue")

		job = self.queue.fetch_job(submission_queue.job_id)
		self.check_status(job, status="finished")

		d.reload()
		self.assertEqual(d.docstatus, 2)

	def test_cancel_on_cancelled_doc(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission

		if not frappe.db.table_exists("Test Submission Queue", cached=False):
			doc = new_doctype("Test Submission Queue", is_submittable=True, queue_in_background=True)
			doc.insert()

		d = frappe.new_doc("Test Submission Queue")
		d.update({"some_fieldname": "Random"})
		d.insert()
		d.submit()
		frappe.db.commit()

		existing = frappe.get_doc(
			{
				"doctype": "Submission Queue",
				"ref_doctype": d.doctype,
				"ref_docname": d.name,
				"status": "Queued",
			}
		)
		existing.insert(d, "Cancel")
		frappe.db.commit()

		initial_count = frappe.db.count(
			"Submission Queue", {"ref_doctype": d.doctype, "ref_docname": d.name, "status": "Queued"}
		)

		queue_submission(d, "Cancel")

		final_count = frappe.db.count(
			"Submission Queue", {"ref_doctype": d.doctype, "ref_docname": d.name, "status": "Queued"}
		)

		self.assertEqual(initial_count, final_count)

		existing.delete(ignore_permissions=True)
		frappe.db.commit()
