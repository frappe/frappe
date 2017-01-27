# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import os, json, csv
from frappe.utils import encode

from openpyxl import load_workbook

# test_records = frappe.get_test_records('Data Import')

class TestDataImport(unittest.TestCase):
	'''
	def test_preview_data_and_column(self):
		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_csv_file.csv")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.save()
		doc.set_preview_data(file_path)

		self.assertTrue(doc.preview_data)
		self.assertTrue(doc.selected_columns)
	'''

	def test_raw_file(self):
		pass
		'''
		print "in test raw files"

		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_xlsx_raw.xlsx")

		doc = frappe.new_doc("Data Import")
		doc.reference_doctype = "User"
		doc.import_file = file_path
		doc.save()
		doc.selected_row = 2
		doc.selected_columns = json.dumps(["first_name","last_name","gender","phone","email"])
		doc.file_import(file_path)
		print frappe.get_all("User")
		while(not doc.freeze_doctype):
			continue
		print doc.log_details
		
		# self.assertTrue(json.loads(doc.log_details))

		# status = insert_into_db("Student Applicant", doc.selected_columns, 1, file_path=file_path)

		# wb = load_workbook(filename=file_path, read_only=True)
		# ws = wb.active

		# for row in ws.iter_rows(min_row=doc.selected_row+1):
		# 	tmp_list = []
		# 	for cell in row:
		# 		tmp_list.append(cell.value)
		# 	self.assertTrue(frappe.get_all(
		# 		doc.reference_doctype, filters={
		# 			"first_name": tmp_list[0],
		# 			"last_name": tmp_list[1],
		# 			"gender": tmp_list[2],
		# 			"student_mobile_number": tmp_list[3],
		# 			"student_email_id": tmp_list[4],
		# 			"program": tmp_list[5]
		# 			}
		# 		))
		'''

	def test_csv_template(self):
		pass
		
		'''
		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_user_csv_template.csv")

		with open(encode(file_path), 'r') as f:
			fcontent = f.read()
		fcontent = fcontent.encode("utf-8").splitlines(True)

		rows = []
		for row in csv.reader(fcontent):
			r = []
			for val in row:
				val = unicode(val, "utf-8").strip()
				if val=="":
					r.append(None)
				else:
					r.append(val)
			rows.append(r)

		log_messages = insert_into_db(reference_doctype="User", file_path=file_path, doc_name="Data Import", only_new_records=0, only_update=0,
			submit_after_import=0, ignore_encoding_errors=0, no_email=1, selected_columns=None, selected_row=None, template=1, rows=rows)
		print log_messages
		'''

	def test_xlsx_template(self):
		pass
		
		'''
		file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_xlsx_template.xlsx")

		log_messages = insert_into_db(reference_doctype="Customer", file_path=file_path, doc_name="Data Import", only_new_records=0, only_update=0,
			submit_after_import=0, ignore_encoding_errors=0, no_email=1, selected_columns=None, selected_row=None, template="template")
		print log_messages
		'''