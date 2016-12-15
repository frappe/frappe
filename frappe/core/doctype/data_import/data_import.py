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
	def validate(self):
		pass
		# print "===============>>>>>> TEST"
		# if self.import_file:
		# 	file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+self.import_file

		# 	wb = load_workbook(filename=file_path, read_only=True)
		# 	ws = wb.active

		# 	excel_file = []
		# 	for row in ws.iter_rows(max_row=10):
		# 		tmp_list = []
		# 		for cell in row:
		# 			tmp_list.append(cell.value)
		# 		excel_file.append(tmp_list)
		# 	self.preview_data = json.dumps(excel_file)

		# # print excel_file
		# print self
		# frappe.throw("just stop")