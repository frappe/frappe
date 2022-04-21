# Copyright (c) 2021, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import unittest

import frappe
from frappe.tests.ui_test_helpers import create_form_tour


class TestFormTour(unittest.TestCase):
	def test_creation(self):
		create_form_tour()
		self.assertEqual(frappe.db.exists("Form Tour", {"name": "Test Form Tour"}))
