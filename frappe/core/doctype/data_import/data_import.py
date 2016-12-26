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

class DataImport(Document):

	def on_update(self):
		if self.import_file and not self.flag_file_preview:
			file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+self.import_file			
			self.set_preview_data(file_path)
		if self.freeze_doctype == 1:
			self.docstatus = 1

	def set_preview_data(self, file_path):
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
		for row in ws.iter_rows(max_row=1):
			for cell in row:
				column_map.append(self.get_matched_column(cell.value))
		self.selected_columns =  json.dumps(column_map)

	def get_matched_column(self, column_name=None):
		new_doc = frappe.new_doc(self.reference_doctype)
		doc_field = [field.fieldname for field in new_doc.meta.fields if field.fieldtype not in 
					['Section Break','Column Break','HTML','Table','Button','Image','Fold','Heading']]
		max_match = 0
		matched_field = ''
		for field in doc_field:
			seq=difflib.SequenceMatcher(None, str(field), str(column_name))
			d=seq.ratio()*100
			if d > max_match:
				max_match = d
				matched_field = field
		return matched_field


@frappe.whitelist()
def insert_into_db(reference_doctype,selected_columns,selected_row,import_file=None,file_path=None):
	if not file_path:
		file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+import_file
	error = False
	selected_columns = json.loads(selected_columns)
	ref_doc = frappe.new_doc(reference_doctype)

	for field in ref_doc.meta.fields:
		if field.reqd == 1 and field.fieldname not in selected_columns:
			frappe.throw("Please select all required fields to insert")
	wb = load_workbook(filename=file_path, read_only=True)
	ws = wb.active

	start =  int(selected_row)
	for row in ws.iter_rows(min_row=start+1):
		try:
			refr_doc = frappe.new_doc(reference_doctype)
			i = 0
			for cell in row:
				if selected_columns[i]:
					setattr(refr_doc, selected_columns[i], cell.value)
				i = i + 1
			refr_doc.insert()
			refr_doc.save()
		except Exception, e:
			error = True
		if error:
			frappe.db.rollback()
		else:
			frappe.db.commit()
	return True