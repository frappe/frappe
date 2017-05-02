# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe.utils import encode, cstr, cint, flt, comma_or

import openpyxl
from cStringIO import StringIO
from openpyxl.styles import Font

import html2text

# return xlsx file object
def make_xlsx(data, sheet_name):

	wb = openpyxl.Workbook(write_only=True)
	ws = wb.create_sheet(sheet_name, 0)

	row1 = ws.row_dimensions[1]
	row1.font = Font(name='Calibri',bold=True)

	for row in data:
		clean_row = []
		for item in row:
			if isinstance(item, basestring):
				obj = html2text.HTML2Text()
				obj.ignore_links = True
				obj.body_width = 0
				obj = obj.handle(unicode(item or ""))
				obj = obj.rsplit('\n', 1)
				value = obj[0]
			else:
				value = item

			clean_row.append(value)

		ws.append(clean_row)

	xlsx_file = StringIO()
	wb.save(xlsx_file)
	return xlsx_file