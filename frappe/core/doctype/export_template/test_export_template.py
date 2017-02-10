# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.core.doctype.export_template import export_template
from frappe.utils.csvutils import read_csv_content

class TestDataImport(unittest.TestCase):
	def test_export(self):
		export_template.get_template(doctype="User", all_doctypes="No", with_data="No", xlsx_format='0')
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")

	def test_export_with_data(self):
		export_template.get_template(doctype="User", all_doctypes="No", with_data="Yes", xlsx_format='0')
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue("Administrator" in [c[1] for c in content if len(c)>1])

	def test_export_with_all_doctypes(self):
		export_template.get_template(doctype="User", all_doctypes="Yes", with_data="Yes", xlsx_format='0')
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue('"Administrator"' in [c[1] for c in content if len(c)>1])
		self.assertEquals(content[13][0], "DocType:")
		self.assertEquals(content[13][1], "User")
		self.assertTrue("UserRole" in content[13])