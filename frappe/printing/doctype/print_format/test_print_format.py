# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals, print_function

import frappe
import unittest
import re

test_records = frappe.get_test_records('Print Format')

class TestPrintFormat(unittest.TestCase):
	def test_print_user(self, style=None):
		print_html = frappe.get_print("User", "Administrator", style=style)
		self.assertTrue("<label>First Name: </label>" in print_html)
		self.assertTrue(re.findall(r'<div class="col-xs-[^"]*">[\s]*administrator[\s]*</div>', print_html))
		return print_html

	def test_print_user_standard(self):
		print_html = self.test_print_user("Standard")
		self.assertTrue(re.findall(r'\.print-format {[\s]*font-size: 9pt;', print_html))
		self.assertFalse(re.findall(r'th {[\s]*background-color: #eee;[\s]*}', print_html))
		self.assertFalse("font-family: serif;" in print_html)

	def test_print_user_modern(self):
		print_html = self.test_print_user("Modern")
		self.assertTrue("/* modern format: for-test */" in print_html)

	def test_print_user_classic(self):
		print_html = self.test_print_user("Classic")
		self.assertTrue("/* classic format: for-test */" in print_html)
