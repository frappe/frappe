# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe, json
import unittest

test_records = frappe.get_test_records('Report')

class TestReport(unittest.TestCase):
	def test_report_builder(self):
		if not frappe.db.exists('Report', 'User Activity Report'):
			frappe.get_doc(json.loads(user_activity_report)).insert()

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

# test standard report with child table
user_activity_report = '''
 {
  "add_total_row": 0,
  "apply_user_permissions": 1,
  "disabled": 0,
  "docstatus": 0,
  "doctype": "Report",
  "is_standard": "No",
  "javascript": null,
  "json": "{\"filters\":[],\"columns\":[[\"name\",\"User\"],[\"user_type\",\"User\"],[\"first_name\",\"User\"],[\"last_name\",\"User\"],[\"last_active\",\"User\"],[\"role\",\"UserRole\"]],\"sort_by\":\"User.modified\",\"sort_order\":\"desc\",\"sort_by_next\":null,\"sort_order_next\":\"desc\"}",
  "modified": "2016-09-01 02:59:07.728890",
  "module": "Core",
  "name": "User Activity Report",
  "query": null,
  "ref_doctype": "User",
  "report_name": "User Activity Report",
  "report_type": "Report Builder"
 }
'''
