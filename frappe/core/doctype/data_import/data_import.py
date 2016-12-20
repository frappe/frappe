# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import os,json
import difflib

from frappe.utils import get_site_name, get_site_path, get_site_base_path, get_path
from openpyxl import load_workbook
# from frappe.model import no_value_field

class DataImport(Document):

	# flag_preview_data = False

	def validate(self):
		print "===============>>>>>> TEST"
		print self.import_file, self.reference_doctype, self.selected_row
		

	def on_update(self):
		# self.get_data_list()
		if self.import_file and not self.flag_file_preview:# and not flag_preview_data:
			self.set_preview_data()
		if self.preview_data and self.selected_columns and self.selected_row:
			self.insert_into_db()
			self.docstatus = 1

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
		wb = load_workbook(filename=file_path)
		ws = wb.active

		excel_file = []
		for row in ws.iter_rows(max_row=11):
			tmp_list = []
			for cell in row:
				tmp_list.append(cell.value)
			excel_file.append(tmp_list)
		self.preview_data = json.dumps(excel_file)

		column_map = []

		for col in ws.iter_cols():
			tmp_list = []
			for cell in col:
				tmp_list.append(cell.value)
			column_map.append(self.get_data_list(tmp_list))
		self.selected_columns =  json.dumps(column_map)


	def get_data_list(self, list_to_compare=None):
		new_doc = frappe.new_doc(self.reference_doctype)
		mapped_field = 0
		max_sim = 0
		for field in new_doc.meta.fields:
			new_list = []
			if field.fieldtype not in ['Section Break', 'Column Break', 'HTML', 'Table', 
				'Button', 'Image', 'Fold', 'Heading']:
				doc = frappe.get_list(self.reference_doctype,fields=[field.fieldname])
				new_list = [getattr(d, field.fieldname) for d in doc]

			seq=difflib.SequenceMatcher(None, str(new_list), str(list_to_compare))
			d=seq.ratio()*100
			if d > max_sim:
				max_sim = d
				mapped_field = field.fieldname
		return mapped_field