# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from openpyxl import load_workbook
import StringIO

@frappe.whitelist()
def upload():
	if getattr(frappe, "uploaded_file", None):
		with open(frappe.uploaded_file, "r") as upfile:
			fcontent = upfile.read()
	else:
		from frappe.utils.file_manager import get_uploaded_content
		fname, fcontent = get_uploaded_content()
	print "============>>>>>>>>>> TESTING"
	print fname
	output = StringIO.StringIO()
	output.write(fcontent)
	print output
	#print fcontent
	wb = load_workbook(output)
	ws = wb.active
	for row in ws.iter_rows(max_row=10):
		for cell in row:
			print cell.value
	




