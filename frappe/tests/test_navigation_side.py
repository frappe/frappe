# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The `navigation_side` fields on System Settings and User, and how boot carries them."""

import frappe
from frappe.cache_manager import clear_defaults_cache
from frappe.sessions import get_session_info
from frappe.shell.settings import get_panes
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

	def test_a_person_saves_their_own_side_and_reads_it_from_the_session(self):
		with set_user("test@example.com"):
			user = frappe.get_doc("User", "test@example.com")
			user.navigation_side = "end"
			user.save()
			self.assertEqual(get_session_info()["user"]["navigation_side"], "end")

	def test_a_person_cannot_save_another_persons_side(self):
		with set_user("test@example.com"):
			user = frappe.get_doc("User", "Administrator")
			user.navigation_side = "end"
			self.assertRaises(frappe.PermissionError, user.save)

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


def block(user: str, pane: str, key: str) -> dict | None:
	"""A frappe block of the settings dialog as `user` is shown it, or None."""
	with set_user(user):
		panes = get_panes()["panes"]
	return next(
		(
			one
			for each in panes
			if each["app"] == "frappe" and each["key"] == pane
			for one in each["blocks"]
			if one["key"] == key
		),
		None,
	)


class TestNavigationSideBlocks(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_the_profile_appearance_block_binds_the_session_user_and_saves_only_the_side(self):
		one = block("test@example.com", "profile", "appearance")
		self.assertEqual(one["component"], "appearance")
		self.assertEqual(
			one["bindings"], {"user": {"type": "Record", "doctype": "User", "resolver": "session_user"}}
		)
		self.assertEqual(one["fields"], ["navigation_side"])

	def test_the_system_appearance_block_saves_the_site_side_on_its_own(self):
		one = block("Administrator", "system", "appearance")
		self.assertEqual(one["component"], "site-appearance")
		self.assertEqual(one["bindings"], {"site": {"type": "Single", "doctype": "System Settings"}})
		self.assertEqual((one["fields"], one["save_mode"]), (["navigation_side"], "auto"))

	def test_the_system_appearance_block_is_hidden_from_a_plain_desk_user(self):
		plain = frappe.get_doc(
			{
				"doctype": "User",
				"email": "navigation_side_plain@example.com",
				"first_name": "Plain",
				"send_welcome_email": 0,
				"roles": [{"role": "Desk User"}],
			}
		).insert()
		self.assertNotIn("System Manager", frappe.get_roles(plain.name))
		self.assertIsNone(block(plain.name, "system", "appearance"))
		self.assertIsNotNone(block(plain.name, "profile", "appearance"))
