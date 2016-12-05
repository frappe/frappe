# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils.xlsxutils import read_xlsx_content_from_uploaded_file


@frappe.whitelist()
def upload():
	# if getattr(frappe, "uploaded_file", None):
	# 	with open(frappe.uploaded_file, "r") as upfile:
	# 		fcontent = upfile.read()
	# else:
	# 	from frappe.utils.file_manager import get_uploaded_content
	# 	fname, fcontent = get_uploaded_content()
	print "============>>>>>>>>>> TESTING"
	# output = StringIO.StringIO()
	# output.write(fcontent)
	# wb = load_workbook(output)
	# ws = wb.active
	# excel_file_as_list = []
	# for row in ws.iter_rows(max_row=21):
	# 	tmp_list = []
	# 	for cell in row:
	# 		tmp_list.append(cell.value)
	# 	excel_file_as_list.append(tmp_list)
	# return excel_file_as_list
	xlsx_list = read_xlsx_content_from_uploaded_file()
	print xlsx_list
	return xlsx_list[:21]


