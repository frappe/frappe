# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import unittest

import frappe

# test_records = frappe.get_test_records('Error Log')


class TestErrorLog(unittest.TestCase):
	def test_error_log(self):
		"""let's do an error log on error log?"""
		doc = frappe.new_doc("Error Log")
		error = doc.log_error("This is an error")
		self.assertEqual(error.doctype, "Error Log")
