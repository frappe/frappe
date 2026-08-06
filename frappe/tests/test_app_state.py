# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.app_state import (
	clear_cache_after_maintenance,
	filter_out_disabled_doctypes,
	get_app_permission_query_conditions,
	get_disabled_doctypes,
	get_disabled_modules,
	get_module_permission_query_conditions,
	is_disabled_app_filtering_active,
	is_module_disabled,
)
from frappe.model.db_query import DatabaseQuery
from frappe.tests import IntegrationTestCase

MAINTENANCE_FLAGS = (
	"in_install",
	"in_migrate",
	"in_patch",
	"in_import",
	"in_uninstall",
	"in_setup_wizard",
	"in_app_toggle",
)


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


class TestDisabledAppState(IntegrationTestCase):
	"""`frappe` stands in for a disabled app here, because it owns modules on every site."""

	def setUp(self):
		super().setUp()
		self.clear_request_cache()
		self.addCleanup(self.clear_request_cache)

	def clear_request_cache(self):
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()

	@contextmanager
	def disabled(self, *apps: str):
		with patch("frappe.get_disabled_apps", return_value=list(apps)):
			self.clear_request_cache()
			try:
				yield
			finally:
				self.clear_request_cache()

	def test_modules_of_a_disabled_app_are_disabled(self):
		with self.disabled("frappe"):
			self.assertIn("Core", get_disabled_modules())

	def test_no_module_is_disabled_when_no_app_is_disabled(self):
		with self.disabled():
			self.assertEqual(get_disabled_modules(), set())

	def test_doctypes_of_a_disabled_module_are_disabled(self):
		with self.disabled("frappe"):
			self.assertIn("DocType", get_disabled_doctypes())

	def test_is_module_disabled(self):
		with self.disabled("frappe"):
			self.assertTrue(is_module_disabled("Core"))
			self.assertFalse(is_module_disabled("zzz Not A Module"))
			self.assertFalse(is_module_disabled(""))
			self.assertFalse(is_module_disabled(None))

	def test_filter_out_disabled_doctypes(self):
		with self.disabled("frappe"):
			self.assertEqual(
				filter_out_disabled_doctypes(["DocType", "zzz Not A DocType"]), ["zzz Not A DocType"]
			)

		with self.disabled():
			self.assertEqual(filter_out_disabled_doctypes(["DocType"]), ["DocType"])

	def test_a_maintenance_operation_stops_the_filtering(self):
		"""A disabled app must take effect again while the site installs, migrates or imports."""
		for flag in MAINTENANCE_FLAGS:
			with self.subTest(flag=flag), self.disabled("frappe"):
				self.assertTrue(is_disabled_app_filtering_active())
				frappe.flags[flag] = True
				try:
					self.clear_request_cache()
					self.assertFalse(is_disabled_app_filtering_active())
					self.assertEqual(get_disabled_modules(), set())
				finally:
					frappe.flags[flag] = False

	def test_cache_is_cleared_after_maintenance_only_when_an_app_is_disabled(self):
		with self.disabled("frappe"), patch("frappe.clear_cache") as clear_cache:
			clear_cache_after_maintenance()
			clear_cache.assert_called_once()

		with self.disabled(), patch("frappe.clear_cache") as clear_cache:
			clear_cache_after_maintenance()
			clear_cache.assert_not_called()
