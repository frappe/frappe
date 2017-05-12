# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe.utils import encode, cstr, cint, flt, comma_or

import openpyxl
from cStringIO import StringIO
from openpyxl.styles import PatternFill, Alignment, Protection, Font, Color, NamedStyle, Border, Side, colors

import html2text

# return xlsx file object
def make_xlsx(**kwargs):
	kwargs = frappe._dict(kwargs)
	data = kwargs.get("data")
	sheet_name = kwargs.get("file_type")

	wb = openpyxl.Workbook()
	ws = wb.create_sheet(sheet_name, 0)

	def make_headers():
		ws.append([kwargs.get("sheet_name")])
		ws.append(["Report Criteria"])
		if kwargs.file_type == "Query Report":
			for filter in kwargs.get("filters").iteritems():
				ws.append(["", " = ".join(map(str,[frappe.unscrub(filter[0]), filter[1]]))])
		elif kwargs.file_type == "Reportview":
			for filter in kwargs.get("filters"):
				ws.append(["", filter])
		ws.append([])

	def make_rows():
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

	def make_styles():
		# make namedstyles for the header, filter details and columns
		# register the style in the sheet
		header_style = create_style(name="header_style", size=20, color=colors.WHITE, fill_type="solid", fgColor="4286f4")
		wb.add_named_style(header_style)
		details_style = create_style(name="details_style", size=13, color=colors.BLACK, fill_type="solid", fgColor="cccccc")
		wb.add_named_style(details_style)
		column_style = create_style(name="column_style", size=12, color=colors.BLACK)
		wb.add_named_style(column_style)

		# merge cells for the header and column and apply styles
		ws.merge_cells('A1:Z1')
		ws['A1'].style = 'header_style'

		data_row = len(kwargs.get("filters")) + 4
		for i in range(2, data_row):
			s_cell = 'B' + str(i)
			e_cell = 'Z' + str(i)
			ws.merge_cells(s_cell+':'+e_cell)
			ws['A'+str(i)].style = 'details_style'
			ws['B'+str(i)].style = 'details_style'

		for cell in ws[str(data_row) + ":" + str(data_row)]:
			cell.style = 'column_style'

	make_headers()
	make_rows()
	make_styles()

	xlsx_file = StringIO()
	wb.save(xlsx_file)
	return xlsx_file


def create_style(name, size, color, fill_type=None, fgColor="ffffff", font='Calibri', bold=True):
	style = NamedStyle(name=name)
	style.font = Font(name=font, bold=bold, size=size, color=color)
	style.fill = PatternFill(fill_type=fill_type, fgColor=fgColor)
	return style

