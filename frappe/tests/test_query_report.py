# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.utils
from frappe.desk.query_report import build_xlsx_data
from frappe.tests.utils import FrappeTestCase
from frappe.utils.xlsxutils import make_xlsx


class TestQueryReport(FrappeTestCase):
	def test_xlsx_data_with_multiple_datatypes(self):
		"""Test exporting report using rows with multiple datatypes (list, dict)"""

		# Create mock data
		data = frappe._dict()
		data.columns = [
			{"label": "Column A", "fieldname": "column_a", "fieldtype": "Float"},
			{"label": "Column B", "fieldname": "column_b", "width": 100, "fieldtype": "Float"},
			{"label": "Column C", "fieldname": "column_c", "width": 150, "fieldtype": "Duration"},
		]
		data.result = [
			[1.0, 3.0, 600],
			{"column_a": 22.1, "column_b": 21.8, "column_c": 86412},
			{"column_b": 5.1, "column_c": 53234, "column_a": 11.1},
			[3.0, 1.5, 333],
		]

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data, column_widths = build_xlsx_data(data, visible_idx, include_indentation=0)

		self.assertEqual(type(xlsx_data), list)
		self.assertEqual(len(xlsx_data), 4)  # columns + data
		# column widths are divided by 10 to match the scale that is supported by openpyxl
		self.assertListEqual(column_widths, [0, 10, 15])

		for row in xlsx_data:
			self.assertIsInstance(row, list)

		# ensure all types are preserved
		for row in xlsx_data[1:]:
			for cell in row:
				self.assertIsInstance(cell, (int, float))

	def test_xlsx_export_with_composite_cell_value(self):
		"""Test excel export using rows with composite cell value"""

		data = frappe._dict()
		data.columns = [
			{"label": "Column A", "fieldname": "column_a", "fieldtype": "Float"},
			{"label": "Column B", "fieldname": "column_b", "width": 150, "fieldtype": "Data"},
		]
		data.result = [
			[1.0, "Dummy 1"],
			{"column_a": 22.1, "column_b": ["Dummy 1", "Dummy 2"]},  # composite value in column_b
		]

		# Define the visible rows
		visible_idx = [0, 1]

		# Build the result
		xlsx_data, column_widths = build_xlsx_data(data, visible_idx, include_indentation=0)
		# Export to excel
		make_xlsx(xlsx_data, "Query Report", column_widths=column_widths)

		for row in xlsx_data:
			# column_b should be 'str' even with composite cell value
			self.assertEqual(type(row[1]), str)
