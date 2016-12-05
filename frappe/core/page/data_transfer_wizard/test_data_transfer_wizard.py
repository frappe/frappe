# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import frappe.defaults
from frappe.core.page.data_transfer_wizard.import_tool import export_csv
import unittest
import os

class TestDataImportFixtures(unittest.TestCase):
	def setUp(self):
		pass

	#start testing
	def test_ImportedData(self):
		self.assertTrue(True)
		os.remove(path)
