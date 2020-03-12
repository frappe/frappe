# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import frappe
from frappe.core.doctype.data_import.exporter_new import Exporter


class TestExporter(unittest.TestCase):
	def test_exports_mandatory_fields(self):
		e = Exporter('Web Page', export_fields='Mandatory')
		csv_array = e.get_csv_array()
		header_row = csv_array[0]
		self.assertEqual(header_row, ['ID', 'Title'])


	def test_exports_all_fields(self):
		e = Exporter('Web Page', export_fields='All')
		csv_array = e.get_csv_array()
		header = csv_array[0]
		self.assertEqual(len(header), 24)


	def test_exports_selected_fields(self):
		export_fields = {
			'Web Page': ['title', 'route', 'published']
		}
		e = Exporter('Web Page', export_fields=export_fields)
		csv_array = e.get_csv_array()
		header = csv_array[0]
		self.assertEqual(header, ['Title', 'Route', 'Published'])


	def test_exports_data(self):
		e = Exporter('ToDo', export_fields='All', export_data=True)
		todo_records = frappe.db.count('ToDo')
		csv_array = e.get_csv_array()
		self.assertEqual(len(csv_array), todo_records + 1)
