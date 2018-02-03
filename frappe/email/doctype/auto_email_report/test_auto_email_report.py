# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest, json

# test_records = frappe.get_test_records('Auto Email Report')

class TestAutoEmailReport(unittest.TestCase):
	def test_auto_email(self):
		frappe.delete_doc('Auto Email Report', 'Permitted Documents For User')

		auto_email_report = frappe.get_doc(dict(
			doctype='Auto Email Report',
			report='Permitted Documents For User',
			report_type='Script Report',
			user='Administrator',
			enabled=1,
			email_to='test@example.com',
			format='HTML',
			frequency='Daily',
			filters=json.dumps(dict(user='Administrator', doctype='DocType'))
		)).insert()

		data = auto_email_report.get_report_content()
		self.assertTrue('<td>DocShare</td>' in data)
		self.assertTrue('<td>Core</td>' in data)

		auto_email_report.format = 'CSV'

		data = auto_email_report.get_report_content()
		self.assertTrue('"Language","Core"' in data)

		auto_email_report.format = 'XLSX'

		data = auto_email_report.get_report_content()

