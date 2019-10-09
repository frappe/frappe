# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import unittest

import frappe
from frappe.desk.query_report import build_xlsx_data
import frappe.utils


class TestQueryReport(unittest.TestCase):
	def test_xlsx_data_with_multiple_datatypes(self):
		"""Test exporting report using rows with multiple datatypes (list, dict)"""

		# Describe the columns
		columns = {
			0: {"label": "Column A", "fieldname": "column_a"},
			1: {"label": "Column B", "fieldname": "column_b"},
			2: {"label": "Column C", "fieldname": "column_c"}
		}

		# Create mock data
		data = frappe._dict()
		data.columns = ["column_a", "column_b", "column_c"]
		data.result = [
			[1.0, 3.0, 5.5],
			{"column_a": 22.1, "column_b": 21.8, "column_c": 30.2},
			{"column_b": 5.1, "column_c": 9.5, "column_a": 11.1},
			[3.0, 1.5, 7.5],
		]

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data = build_xlsx_data(columns, data, visible_idx, include_indentation=0)

		self.assertEqual(type(xlsx_data), list)
		self.assertEqual(len(xlsx_data), 4)  # columns + data

		for row in xlsx_data:
			self.assertEqual(type(row), list)
