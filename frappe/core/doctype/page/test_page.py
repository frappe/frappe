# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Page')

class TestPage(unittest.TestCase):
	def test_naming(self):
		self.assertRaises(frappe.NameError, frappe.get_doc(dict(doctype='Page', page_name='DocType', module='Core')).insert)
		self.assertRaises(frappe.NameError, frappe.get_doc(dict(doctype='Page', page_name='Settings', module='Core')).insert)
