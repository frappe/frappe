# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe.utils import encode, cstr, cint, flt, comma_or

import openpyxl
from cStringIO import StringIO
from openpyxl.styles import Font
from openpyxl import load_workbook

# return xlsx file object
def make_xlsx(data, sheet_name):
	wb = openpyxl.Workbook(write_only=True)
	ws = wb.create_sheet(sheet_name, 0)

	row1 = ws.row_dimensions[1]
	row1.font = Font(name='Calibri',bold=True)

	for row in data:
		ws.append(row)

	xlsx_file = StringIO()
	wb.save(xlsx_file)
	return xlsx_file


def read_xlsx_from_attached_file(file_path, max_row=None):	
	wb = load_workbook(filename=file_path)
	ws = wb.active

	data = []
	max_randered_row = 25 if (ws.max_row>25 and max_row) else ws.max_row

	for row in ws.iter_rows(max_row=max_randered_row):
		tmp_list = []
		for cell in row:
			tmp_list.append(cell.value)
		if [x for x in tmp_list if x != None]:
			data.append(tmp_list)
	return data

