# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import time

import frappe
from frappe.desk.query_report import generate_report_result, get_report_doc
from frappe.tests.utils import FrappeTestCase


class TestPreparedReport(FrappeTestCase):
	@classmethod
	def tearDownClass(cls):
		for r in frappe.get_all("Prepared Report", pluck="name"):
			frappe.delete_doc("Prepared Report", r, force=True, delete_permanently=True)

		frappe.db.commit()

	def create_prepared_report(self, commit=False):
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
		doc_ = self.create_prepared_report()
		self.assertEqual("Queued", doc_.status)
		self.assertTrue(doc_.queued_at)

		frappe.db.commit()
		time.sleep(5)

		doc_ = frappe.get_last_doc("Prepared Report")
		self.assertEqual("Completed", doc_.status)
		self.assertTrue(doc_.job_id)
		self.assertTrue(doc_.report_end_time)

	def test_prepared_data(self):
		doc_ = self.create_prepared_report(commit=True)
		time.sleep(5)

		prepared_data = json.loads(doc_.get_prepared_data().decode("utf-8"))
		generated_data = generate_report_result(get_report_doc("Database Storage Usage By Tables"))
		self.assertEqual(len(prepared_data["columns"]), len(generated_data["columns"]))
		self.assertEqual(len(prepared_data["result"]), len(generated_data["result"]))
		self.assertEqual(len(prepared_data), len(generated_data))
