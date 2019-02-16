# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe

import openpyxl
import re
from openpyxl.styles import Font
from openpyxl import load_workbook
from six import BytesIO, string_types

ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')
# return xlsx file object
def make_xlsx(data, sheet_name, wb=None):

	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	ws = wb.create_sheet(sheet_name, 0)

	row1 = ws.row_dimensions[1]
	row1.font = Font(name='Calibri',bold=True)

	for row in data:
		clean_row = []
		for item in row:
			if isinstance(item, string_types) and (sheet_name not in ['Data Import Template', 'Data Export']):
				value = handle_html(item)
			else:
				value = item

			if isinstance(item, string_types) and next(ILLEGAL_CHARACTERS_RE.finditer(value), None):
				# Remove illegal characters from the string
				value = re.sub(ILLEGAL_CHARACTERS_RE, '', value)

			clean_row.append(value)

		ws.append(clean_row)

	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	return xlsx_file


def handle_html(data):
	# return if no html tags found
	data = frappe.as_unicode(data)

	if '<' not in data:
		return data
	if '>' not in data:
		return data

	from html2text import HTML2Text

	h = HTML2Text()
	h.unicode_snob = True
	h = h.unescape(data or "")

	obj = HTML2Text()
	obj.ignore_links = True
	obj.body_width = 0
	value = obj.handle(h)
	value = ", ".join(value.split('  \n'))
	value = " ".join(value.split('\n'))
	value = ", ".join(value.split('# '))
	return value

def read_xlsx_file_from_attached_file(file_id=None, fcontent=None, filepath=None):
	if file_id:
		from frappe.utils.file_manager import get_file_path
		filename = get_file_path(file_id)
	elif fcontent:
		from io import BytesIO
		filename = BytesIO(fcontent)
	elif filepath:
		filename = filepath
	else:
		return

	rows = []
	wb1 = load_workbook(filename=filename, read_only=True, data_only=True)
	ws1 = wb1.active
	for row in ws1.iter_rows():
		tmp_list = []
		for cell in row:
			tmp_list.append(cell.value)
		rows.append(tmp_list)
	return rows
