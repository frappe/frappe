# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""D12's attention channel -- the one-time invitation to try the new navigation.

A grid-mode site is asked once and never again, whichever way it answers. A fresh install is
already on Apps, so it is never asked at all -- which is why this needs no patch.
"""

from contextlib import contextmanager

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import APPS, DESKTOP_ICONS
from frappe.tests import IntegrationTestCase
from frappe.tests.test_icon_grid_containment import desktop_page
from frappe.utils.new_navigation_nudge import (
	SKIP_NEW_NAVIGATION_PROMPT,
	should_show_new_navigation_prompt,
	submit_new_navigation_prompt,
)

USER = "test-nav-nudge@example.com"
MANAGER = "test-nav-nudge-manager@example.com"


@contextmanager
def unasked():
	"""The site as it arrives from the upgrade: on the grid, never asked."""
	frappe.defaults.clear_default(SKIP_NEW_NAVIGATION_PROMPT)
	with desktop_page(DESKTOP_ICONS):
		yield
	frappe.defaults.clear_default(SKIP_NEW_NAVIGATION_PROMPT)


@contextmanager
def as_user(user: str):
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user("Administrator")


class TestNewNavigationNudge(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for email, roles in ((USER, ["Desk User"]), (MANAGER, ["Workspace Manager"])):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in roles],
				}
			).insert(ignore_if_duplicate=True)

	def test_a_grid_site_asks_a_system_manager(self):
		with unasked():
			self.assertTrue(should_show_new_navigation_prompt())

	def test_a_grid_site_asks_a_workspace_manager_too(self):
		"""The one exception to Workspace-Manager-only: which desktop *screen* a site shows is
		a system setting, and a role granted to nobody by default would ask nobody."""
		with unasked(), as_user(MANAGER):
			self.assertTrue(should_show_new_navigation_prompt())

	def test_it_asks_nobody_else(self):
		with unasked(), as_user(USER):
			self.assertFalse(should_show_new_navigation_prompt())

	def test_a_site_already_on_apps_is_never_asked(self):
		"""Which is also why a fresh install never sees it, and why no patch is needed: a new
		site is on Apps from the first boot, so the condition is false before anything runs."""
		frappe.defaults.clear_default(SKIP_NEW_NAVIGATION_PROMPT)
		with desktop_page(APPS):
			self.assertFalse(should_show_new_navigation_prompt())

	def test_declining_is_terminal(self):
		with unasked():
			self.assertEqual(submit_new_navigation_prompt("keep_icon_grid"), "kept")

			self.assertFalse(should_show_new_navigation_prompt())
			# and the site is left exactly where it was
			self.assertEqual(frappe.db.get_single_value("Desktop Settings", "desktop_page"), DESKTOP_ICONS)

	def test_accepting_switches_the_site_and_is_terminal_too(self):
		with unasked():
			self.assertEqual(submit_new_navigation_prompt("try_new_navigation"), "switched")

			self.assertEqual(frappe.db.get_single_value("Desktop Settings", "desktop_page"), APPS)
			self.assertFalse(should_show_new_navigation_prompt())

	def test_accepting_deletes_no_icons(self):
		"""What makes "try it" honest: switching back from Desktop Settings finds the grid
		exactly as it was."""
		with unasked():
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": "Nudge Test Icon",
					"icon_type": "Folder",
					"link_type": "External",
				}
			).insert(ignore_permissions=True)

			submit_new_navigation_prompt("try_new_navigation")

			self.assertTrue(frappe.db.exists("Desktop Icon", {"label": "Nudge Test Icon"}))

	def test_someone_without_either_role_cannot_answer_for_the_site(self):
		with unasked(), as_user(USER), self.assertRaises(frappe.PermissionError):
			submit_new_navigation_prompt("try_new_navigation")

	def test_neither_flag_is_a_schema_change(self):
		"""Both live outside the schema on purpose -- a `frappe.defaults` key and a boot key --
		so a mechanism with an end date leaves no column behind when it goes."""
		self.assertFalse(frappe.get_meta("Desktop Settings").get_field(SKIP_NEW_NAVIGATION_PROMPT))
		self.assertFalse(frappe.db.exists("DocField", {"fieldname": SKIP_NEW_NAVIGATION_PROMPT}))

	def test_the_boot_carries_the_flag(self):
		"""How the dialog ever gets a chance to appear: one key on the boot, read by the desk
		on the same schedule as the other one-time prompt."""
		from frappe.sessions import get as get_session

		with unasked():
			frappe.cache.hdel("bootinfo", frappe.session.user)
			# `get` reads it to decide whether to attach the change log; a test has no request
			frappe.local.request = None
			self.assertTrue(get_session().get("show_new_navigation_prompt"))
