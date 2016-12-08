# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils.xlsxutils import read_xlsx_content_from_uploaded_file


@frappe.whitelist()
def upload_data():
	print "============>>>>>>>>>> TESTING"
	xlsx_list = read_xlsx_content_from_uploaded_file()
	return xlsx_list[:21]

@frappe.whitelist()
def import_data():
	print "in import function"



