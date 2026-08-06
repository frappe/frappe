# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.app_state import (
	get_app_permission_query_conditions,
	get_module_permission_query_conditions,
)
from frappe.model.db_query import DatabaseQuery
from frappe.tests import IntegrationTestCase


class TestDisabledAppPermissionConditions(IntegrationTestCase):
	def test_no_condition_when_nothing_is_disabled(self):
		with patch("frappe.app_state.get_disabled_modules", return_value=set()):
			self.assertIsNone(get_module_permission_query_conditions("Administrator", doctype="Print Format"))

		with patch("frappe.get_disabled_apps", return_value=[]):
			self.assertIsNone(get_app_permission_query_conditions("Administrator", doctype="Desktop Icon"))

	def test_disabled_module_records_are_hidden(self):
		hidden = self.new_print_format(module="Core")
		visible = self.new_print_format(module="Custom")

		with patch("frappe.app_state.get_disabled_modules", return_value={"Core"}):
			names = frappe.get_list("Print Format", pluck="name", limit_page_length=0)

		self.assertNotIn(hidden, names)
		self.assertIn(visible, names)

	def test_records_without_a_module_stay_visible(self):
		"""`module not in (...)` is NULL for an unset module, so the column needs an IFNULL guard."""
		without_module = self.new_print_format(module=None)

		with patch("frappe.app_state.get_disabled_modules", return_value={"Core"}):
			names = frappe.get_list("Print Format", pluck="name", limit_page_length=0)
			legacy = DatabaseQuery("Print Format").execute(fields=["name"], limit_page_length=0)

		self.assertIn(without_module, names)
		self.assertIn(without_module, [row.name for row in legacy])

	def new_print_format(self, module: str | None) -> str:
		print_format = frappe.get_doc(
			doctype="Print Format", name=frappe.generate_hash(length=10), module=module, standard="No"
		).insert()
		return print_format.name
