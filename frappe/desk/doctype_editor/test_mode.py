# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.doctype_editor.mode import mode_refusal
from frappe.desk.doctype_editor.save import save_doctype_editor
from frappe.desk.doctype_editor.test_save_design import delete_committed, make_custom_doctype
from frappe.desk.doctype_editor.versions import base_version
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

	def test_design_on_a_standard_doctype_needs_developer_mode(self):
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertIn("needs developer mode", mode_refusal("ToDo", "Design"))
			with self.assertRaises(frappe.PermissionError):
				save_doctype_editor("ToDo", "Design", base_version("ToDo"), [])

	def test_design_needs_the_system_manager_role(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Guest")
		self.assertIn("System Manager", mode_refusal("ToDo", "Design"))
