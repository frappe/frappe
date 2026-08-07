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

	def test_icon_clears_only_the_grids_it_appears_on(self):
		"""A user's own icon is on no one else's desk, so it must not evict their grids."""
		other = "someone.else@example.com"
		icon = frappe.new_doc("Desktop Icon")
		icon.label = "Cache Scope Test"
		icon.icon_type = "Link"

		icon.standard = 0
		icon.owner = "owner@example.com"
		frappe.cache.hset("desktop_icons", other, [])
		icon.clear_icon_cache()
		self.assertIsNotNone(frappe.cache.hget("desktop_icons", other))

		# an Administrator-owned icon is served to every user, so every grid goes
		icon.owner = "Administrator"
		icon.clear_icon_cache()
		self.assertIsNone(frappe.cache.hget("desktop_icons", other))
