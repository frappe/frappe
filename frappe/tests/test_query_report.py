# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest

import frappe
import json
from frappe.desk.query_report import build_xlsx_data, save_report, delete_report
from frappe.core.doctype.user_permission.test_user_permission import create_user
import frappe.utils


class TestQueryReport(unittest.TestCase):
	def test_xlsx_data_with_multiple_datatypes(self):
		"""Test exporting report using rows with multiple datatypes (list, dict)"""

		# Describe the columns
		columns = {
			0: {"label": "Column A", "fieldname": "column_a"},
			1: {"label": "Column B", "fieldname": "column_b"},
			2: {"label": "Column C", "fieldname": "column_c"},
		}

		# Create mock data
		data = frappe._dict()
		data.columns = [
			{"label": "Column A", "fieldname": "column_a"},
			{"label": "Column B", "fieldname": "column_b", "width": 150},
			{"label": "Column C", "fieldname": "column_c", "width": 100},
		]
		data.result = [
			[1.0, 3.0, 5.5],
			{"column_a": 22.1, "column_b": 21.8, "column_c": 30.2},
			{"column_b": 5.1, "column_c": 9.5, "column_a": 11.1},
			[3.0, 1.5, 7.5],
		]

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data, column_widths = build_xlsx_data(
			columns, data, visible_idx, include_indentation=0
		)

		self.assertEqual(type(xlsx_data), list)
		self.assertEqual(len(xlsx_data), 4)  # columns + data
		# column widths are divided by 10 to match the scale that is supported by openpyxl
		self.assertListEqual(column_widths, [0, 15, 10])

		for row in xlsx_data:
			self.assertEqual(type(row), list)

	def test_save_or_delete_report(self):
		"""Test for validations when editing / deleting report of type Query/Script/Custom Report"""

		try:
			report = frappe.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": "Test Query Report",
					"report_type": "Query Report",
					"is_standard": "No",
					"query": "select *from `tabUser` where enabled=1; "
				}
			).insert()

			# Check for PermissionError
			create_user("test_report_owner@example.com", "_Test Role")
			frappe.set_user("test_report_owner@example.com")
			self.assertRaises(frappe.PermissionError, delete_report, report.name)

			# Check for Report Type
			frappe.set_user("Administrator")
			report.db_set("report_type", "Report Builder")
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Reports of type Report Builder can not be deleted",
				delete_report,
				report.name,
			)

			# Check if creating and deleting works with proper validations
			frappe.set_user("test_report_owner@example.com")
			report_name = save_report(
				"Test Query Report",
				"Dummy Report",
				json.dumps(
					[
						{
							"fieldname": "email",
							"fieldtype": "Data",
							"label": "Email",
							"insert_after_index": 0,
							"link_field": "name",
							"doctype": "User",
							"options": "Email",
							"width": 100,
							"id": "email",
							"name": "Email",
						}
					]
				),
			)

			doc = frappe.get_doc("Report", report_name)
			delete_report(doc.name)

		finally:
			frappe.set_user("Administrator")
			frappe.db.rollback()
