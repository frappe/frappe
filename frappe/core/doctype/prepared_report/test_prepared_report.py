# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import time

import frappe
from frappe.desk.query_report import generate_report_result, get_report_doc
from frappe.tests.utils import FrappeTestCase, timeout


class TestPreparedReport(FrappeTestCase):
	@classmethod
	def tearDownClass(cls):
		for r in frappe.get_all("Prepared Report", pluck="name"):
			frappe.delete_doc("Prepared Report", r, force=True, delete_permanently=True)

		frappe.db.commit()

	@timeout(seconds=20)
	def wait_for_completion(self, report, status="Completed"):
		frappe.db.commit()  # Flush changes first
		while True:
			frappe.db.rollback()  # read new data
			report.reload()
			if report.status == status:
				break
			# Cheap blocking behaviour
			time.sleep(0.5)

	def create_prepared_report(self, commit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Prepared Report",
				"report_name": "Database Storage Usage By Tables",
			}
		).insert()

		if commit:
			frappe.db.commit()

		return doc

	def test_queueing(self):
		doc = self.create_prepared_report()
		self.assertEqual("Queued", doc.status)
		self.assertTrue(doc.queued_at)

		self.wait_for_completion(doc)

		doc = frappe.get_last_doc("Prepared Report")
		self.assertTrue(doc.job_id)
		self.assertTrue(doc.report_end_time)

	def test_prepared_data(self):
		doc = self.create_prepared_report()
		self.wait_for_completion(doc)

		prepared_data = json.loads(doc.get_prepared_data().decode("utf-8"))
		generated_data = generate_report_result(get_report_doc("Database Storage Usage By Tables"))
		self.assertEqual(len(prepared_data["columns"]), len(generated_data["columns"]))
		self.assertEqual(len(prepared_data["result"]), len(generated_data["result"]))
		self.assertEqual(len(prepared_data), len(generated_data))
