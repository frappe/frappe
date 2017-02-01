# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import os, json, csv
from frappe.utils import encode

from openpyxl import load_workbook

from frappe.core.doctype.data_import.data_import import import_raw, import_template


class TestDataImport(unittest.TestCase):

	def test_preview_data_and_column(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_xlsx_raw.xlsx")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.import_file = file_path

		doc.save()
		doc.set_preview_data(file_path)
		self.assertTrue(doc.preview_data)
		self.assertTrue(doc.selected_columns)


	def test_raw_file(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_xlsx_raw.xlsx")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.import_file = file_path
		doc.selected_row = 2
		doc.selected_columns = json.dumps(["first_name","last_name","gender","phone","email"])
		doc.submit_after_import = 0
		doc.no_email = 1
		doc.template = "raw"

		doc.save()
		self.assertTrue(import_raw(doc_name=doc.name, file_path=file_path))


	def test_csv_template(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_csv_template.csv")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.submit_after_import = 0
		doc.no_email = 1
		doc.template = "template"
		doc.ignore_encoding_errors = 0
		doc.only_new_records = 0
		doc.only_update = 0

		doc.save()

		rows = []
		with open(encode(file_path), 'r') as f:
			content = f.read()
			fcontent = content.encode("utf-8").splitlines(True)
			for row in csv.reader(fcontent):
				r = []
				for val in row:
					val = unicode(val, "utf-8").strip()
					if val=="":
						r.append(None)
					else:
						r.append(val)
				rows.append(r)
		
		self.assertTrue(import_template(doc_name=doc.name, file_path=file_path, rows=rows))


	def test_xlsx_template(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_xlsx_template.xlsx")
		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.submit_after_import = 0
		doc.no_email = 1
		doc.template = "template"
		doc.ignore_encoding_errors = 0
		doc.only_new_records = 0
		doc.only_update = 0
		
		doc.save()
		self.assertTrue(import_template(doc_name=doc.name, file_path=file_path))