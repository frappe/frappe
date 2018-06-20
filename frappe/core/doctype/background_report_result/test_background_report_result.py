# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
import json
import time

import frappe
import unittest
from frappe.desk.query_report import background_enqueue_run


class TestBackgroundReportResult(unittest.TestCase):

	def setUp(self):
		self.report = frappe.get_doc({
			"doctype": "Report",
			"name": "Permitted Documents For User"
		})
		self.filters = {
			"user": "Administrator",
			"doctype": "Role"
		}
		self.background_report_doc = frappe.get_doc({
			"doctype": "Background Report Result",
			"report_name": self.report.name,
			"filters": json.dumps(self.filters),
			"ref_report_doctype": self.report.name,
			"report_type": self.report.report_type,
			"query": self.report.query,
			"module": self.report.module
		}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.background_report_doc.delete()

	def test_for_creation(self):
		self.assertTrue('QUEUED' == self.background_report_doc.status.upper())
		self.assertTrue(self.background_report_doc.report_start_time)

	def test_for_completion(self):
		background_enqueue_run(self.background_report_doc.report_name, self.filters, 'Administrator')
		time.sleep(5)
		self.result = frappe.get_doc("Background Report Result", self.background_report_doc.name)
		self.assertTrue('COMPLETED' == self.result.status.upper())
		self.assertTrue(self.result.report_end_time)
		self.assertGreater(
			len(frappe.desk.form.load.get_attachments(
				dt="Background Report Result", dn=self.result.name)), 0)
