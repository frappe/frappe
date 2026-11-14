# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The `navigation_side` fields on System Settings and User, and how boot carries them."""

import frappe
from frappe.cache_manager import clear_defaults_cache
from frappe.sessions import get_session_info
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


class TestNavigationSide(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(user="Administrator")
		clear_defaults_cache("__default")

	def test_the_site_field_defaults_to_start(self):
		self.assertEqual(frappe.get_meta("System Settings").get_field("navigation_side").default, "start")

	def test_the_user_field_is_blank_by_default(self):
		self.assertFalse(frappe.get_meta("User").get_field("navigation_side").default)

	def test_session_carries_a_blank_user_side_as_an_empty_string(self):
		frappe.db.set_value("User", "Administrator", "navigation_side", None)
		frappe.clear_cache(user="Administrator")
		self.assertEqual(get_session_info()["user"]["navigation_side"], "")

	def test_session_carries_the_user_side(self):
		frappe.db.set_value("User", "Administrator", "navigation_side", "end")
		frappe.clear_cache(user="Administrator")
		self.assertEqual(get_session_info()["user"]["navigation_side"], "end")

	def test_session_carries_each_person_their_own_side(self):
		frappe.db.set_value("User", "Administrator", "navigation_side", "end")
		frappe.clear_cache(user="Administrator")
		with set_user("test@example.com"):
			self.assertEqual(get_session_info()["user"]["navigation_side"], "")

	def test_a_system_settings_save_puts_the_side_in_the_site_defaults(self):
		settings = frappe.get_doc("System Settings")
		settings.navigation_side = "start"
		settings.save()
		settings.navigation_side = "end"
		settings.save()
		self.assertEqual(frappe.defaults.get_defaults()["navigation_side"], "end")
		self.assertEqual(get_session_info()["defaults"]["navigation_side"], "end")

	def test_system_settings_refuses_another_value(self):
		settings = frappe.get_doc("System Settings")
		settings.navigation_side = "left"
		self.assertRaises(frappe.ValidationError, settings.save)

	def test_user_refuses_another_value(self):
		user = frappe.get_doc("User", "Administrator")
		user.navigation_side = "right"
		self.assertRaises(frappe.ValidationError, user.save)

	def test_user_accepts_blank_start_and_end(self):
		user = frappe.get_doc("User", "Administrator")
		for side in ("", "start", "end"):
			user.navigation_side = side
			user.save()
