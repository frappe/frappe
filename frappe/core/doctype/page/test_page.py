# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase

test_records = frappe.get_test_records("Page")


class TestPage(FrappeTestCase):
	def test_naming(self):
		self.assertRaises(
			frappe.NameError,
			frappe.get_doc(dict(doctype="Page", page_name="DocType", module="Core")).insert,
		)
		self.assertRaises(
			frappe.NameError,
			frappe.get_doc(dict(doctype="Page", page_name="Settings", module="Core")).insert,
		)
