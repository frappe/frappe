# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# from frappe.core.doctype.data_import.data_import import get_data_list

# test_records = frappe.get_test_records('Data Import')

class TestDataImport(unittest.TestCase):
	def test_matching(self):

		doc = frappe.new_doc("Data Import")

		doc.reference_doctype = "Student Applicant"
		doc.import_file = "/private/files/test (copy).xlsx"

		doc.save()

		# new_doc = frappe.get_all("Student Applicant")

		# print doc


