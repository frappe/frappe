# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import os

from frappe.utils import get_site_name, get_site_path, get_site_base_path, get_path
from openpyxl import load_workbook


class DataImport(Document):
	def on_update(self):
		print "===============>>>>>> TEST"
		file_path = os.getcwd()+get_site_path()[1:].encode('utf8')+self.import_file

		wb = load_workbook(filename=file_path, read_only=True)
		ws = wb.active

		excel_file_as_list = []
		for row in ws.iter_rows(max_row=20):
			excel_file_as_list.append([cell.value for cell in row])
		self.file_preview = excel_file_as_list