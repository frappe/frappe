# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import os,json

from frappe.utils import get_site_name, get_site_path, get_site_base_path, get_path
from openpyxl import load_workbook


class DataImport(Document):

	# flag_preview_data = False

	def validate(self):
		print "===============>>>>>> TEST"
		if self.import_file:# and not flag_preview_data:
			self.set_preview_data()

	def on_update(self):
		print self.import_file, self.reference_doctype, self.selected_row
		if self.preview_data and self.selected_columns and self.selected_row:
			self.insert_into_db()
			self.docstatus = 1
		# frappe.throw("just stop")

	def insert_into_db(self):
		error = False
		selected_columns = json.loads(self.selected_columns)
		doc = frappe.new_doc(self.reference_doctype)

		for field in doc.meta.fields:
			if field.reqd == 1 and field.fieldname not in selected_columns:
				frappe.throw("Please select all required fields to insert")

		file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+self.import_file
		wb = load_workbook(filename=file_path, read_only=True)
		ws = wb.active

		start =  int(self.selected_row)
		for row in ws.iter_rows(min_row=start+1):
			try:
				doc = frappe.new_doc(self.reference_doctype)
				i = 0
				for cell in row:
					if selected_columns[i]:
						setattr(doc, selected_columns[i], cell.value)
					i = i + 1
				doc.insert()
				doc.save()
			except Exception, e:
				error = True
			if error:
				frappe.db.rollback()
			else:
				frappe.db.commit()

	def set_preview_data(self):
		file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+self.import_file
		wb = load_workbook(filename=file_path, read_only=True)
		ws = wb.active

		excel_file = []
		for row in ws.iter_rows(max_row=15):
			tmp_list = []
			for cell in row:
				tmp_list.append(cell.value)
			excel_file.append(tmp_list)
		self.preview_data = json.dumps(excel_file)
		# flag_preview_data = True
