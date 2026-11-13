# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype_editor.mode import mode_refusal
from frappe.desk.doctype_editor.test_save_design import delete_committed, make_custom_doctype
from frappe.tests import IntegrationTestCase

DOCTYPE = "Test Editor Mode 47271"


class TestModeRefusal(IntegrationTestCase):
	def test_a_custom_doctype_refuses_customize(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)
		self.assertIn("always opens in Design mode", mode_refusal(DOCTYPE, "Customize"))
		self.assertIsNone(mode_refusal(DOCTYPE, "Design"))

	def test_a_core_doctype_refuses_customize(self):
		self.assertIn("cannot be customized", mode_refusal("DocType", "Customize"))

	def test_a_standard_doctype_opens_in_customize(self):
		self.assertIsNone(mode_refusal("ToDo", "Customize"))
