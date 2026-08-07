# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestDesktopIcon(IntegrationTestCase):
	"""
	Integration tests for DesktopIcon.
	Use this class for testing interactions between multiple components.
	"""

	def test_clearing_cache_without_user_clears_every_user(self):
		"""An icon change invalidates the whole grid cache, not just the session user's."""
		frappe.cache.hset("desktop_icons", "someone.else@example.com", [])
		frappe.cache.hset("desktop_icons", frappe.session.user, [])

		clear_desktop_icons_cache()

		self.assertIsNone(frappe.cache.hget("desktop_icons", "someone.else@example.com"))
		self.assertIsNone(frappe.cache.hget("desktop_icons", frappe.session.user))

	def test_clearing_cache_for_one_user_leaves_others(self):
		frappe.cache.hset("desktop_icons", "someone.else@example.com", [])
		frappe.cache.hset("desktop_icons", frappe.session.user, [])

		clear_desktop_icons_cache(user=frappe.session.user)

		self.assertIsNotNone(frappe.cache.hget("desktop_icons", "someone.else@example.com"))
		self.assertIsNone(frappe.cache.hget("desktop_icons", frappe.session.user))
