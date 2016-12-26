# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import os, json

from openpyxl import load_workbook

from frappe.core.doctype.data_import.data_import import insert_into_db

# test_records = frappe.get_test_records('Data Import')

class TestDataImport(unittest.TestCase):
	def test_preview_data_and_column(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_file.xlsx")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "Student Applicant"

		doc.set_preview_data(file_path)

		self.assertTrue(doc.preview_data)

		self.assertTrue(doc.selected_columns)

		# doc.save()
		# new_doc = frappe.get_all("Student Applicant")
		# print doc

	def test_insertion(self):

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_file.xlsx")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "Student Applicant"
		doc.selected_columns = json.dumps(["first_name", "last_name", "gender", 
			"student_mobile_number", "student_email_id", "program"])
		doc.selected_row = 1

		status = insert_into_db("Student Applicant",doc.selected_columns,1,file_path=file_path)

		wb = load_workbook(filename=file_path, read_only=True)
		ws = wb.active

		for row in ws.iter_rows(min_row=doc.selected_row+1):
			tmp_list = []
			for cell in row:
				tmp_list.append(cell.value)
			self.assertTrue(frappe.get_all(
				doc.reference_doctype, filters={
					"first_name": tmp_list[0],
					"last_name": tmp_list[1],
					"gender": tmp_list[2],
					"student_mobile_number": tmp_list[3],
					"student_email_id": tmp_list[4],
					"program": tmp_list[5]
					}
				))


