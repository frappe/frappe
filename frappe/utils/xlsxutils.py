# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe.utils import encode, cstr, cint, flt, comma_or

import openpyxl
from cStringIO import StringIO
from openpyxl.styles import Font

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