# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import json


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
		self.assertEqual('Queued'.upper(), self.background_report_doc.status)
		self.assertTrue(self.background_report_doc.report_start_time)
		self.assertTrue(frappe.db.exists("Report", {"ref_report_doctype": self.report.name}))
