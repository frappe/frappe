# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import json
import time

from frappe.core.doctype.prepared_report.prepared_report import run_background


class TestPreparedReport(unittest.TestCase):
	def setUp(self):
		self.report = frappe.get_doc({
			"doctype": "Report",
			"name": "Permitted Documents For User"
		})
		self.filters = {
			"user": "Administrator",
			"doctype": "Role"
		}
		self.prepared_report_doc = frappe.get_doc({
			"doctype": "Prepared Report",
			"report_name": self.report.name,
			"filters": json.dumps(self.filters),
			"ref_report_doctype": self.report.name
		}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.prepared_report_doc.delete()

	def test_for_creation(self):
		self.assertTrue('QUEUED' == self.prepared_report_doc.status.upper())
		self.assertTrue(self.prepared_report_doc.report_start_time)

	def test_for_completion(self):
		run_background(self.prepared_report_doc)
		time.sleep(5)
		self.result = frappe.get_doc("Prepared Report", self.prepared_report_doc.name)
		self.assertTrue('COMPLETED' == self.result.status.upper())
		self.assertTrue(self.result.report_end_time)
		self.assertGreater(
			len(frappe.desk.form.load.get_attachments(
				dt="Prepared Report", dn=self.result.name)), 0)

