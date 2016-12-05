# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from frappe import msgprint, _
import json, csv
from frappe.utils import encode, cstr, cint, flt, comma_or
import frappe, xlwt, StringIO, datetime

from openpyxl import load_workbook

def read_xlsx_content_from_uploaded_file(ignore_encoding=False):
	if getattr(frappe, "uploaded_file", None):
		with open(frappe.uploaded_file, "r") as upfile:
			fcontent = upfile.read()
	else:
		from frappe.utils.file_manager import get_uploaded_content
		fname, fcontent = get_uploaded_content()
	return read_xlsx_content_as_list(fcontent, ignore_encoding)

def read_xlsx_content_as_list(fcontent, ignore_encoding=False):
	xlsx_file_as_list = []	

	# if not isinstance(fcontent, unicode):
	# 	decoded = False
	# 	for encoding in ["utf-8", "windows-1250", "windows-1252"]:
	# 		try:
	# 			fcontent = unicode(fcontent, encoding)
	# 			decoded = True
	# 			break
	# 		except UnicodeDecodeError:
	# 			continue

	# 	if not decoded:
	# 		frappe.msgprint(_("Unknown file encoding. Tried utf-8, windows-1250, windows-1252."),
	#			raise_exception=True)

	output = StringIO.StringIO()
	output.write(fcontent)

	wb = load_workbook(output)
	ws = wb.active

	for row in ws.iter_rows():
		tmp_list = []
		for cell in row:
			tmp_list.append(cell.value)
		xlsx_file_as_list.append(tmp_list)
	print "i am here"
	return xlsx_file_as_list