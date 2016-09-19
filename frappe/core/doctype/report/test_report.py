# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe, json, os
import unittest

test_records = frappe.get_test_records('Report')

class TestReport(unittest.TestCase):
	def test_report_builder(self):
		if frappe.db.exists('Report', 'User Activity Report'):
			frappe.delete_doc('Report', 'User Activity Report')

		with open(os.path.join(os.path.dirname(__file__), 'user_activity_report.json'), 'r') as f:
			frappe.get_doc(json.loads(f.read())).insert()

		report = frappe.get_doc('Report', 'User Activity Report')
		data = report.get_data()
		self.assertEquals(data[0][0], 'ID')
		self.assertEquals(data[0][1], 'User Type')
		self.assertTrue('Administrator' in [d[0] for d in data])

	def test_query_report(self):
		report = frappe.get_doc('Report', 'Permitted Documents For User')
		data = report.get_data(filters={'user': 'Administrator', 'doctype': 'DocType'})
		self.assertEquals(data[0][0], 'Name')
		self.assertEquals(data[0][1], 'Module')
		self.assertTrue('User' in [d[0] for d in data])

