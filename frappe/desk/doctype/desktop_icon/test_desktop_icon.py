# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

from contextlib import contextmanager

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import create_desktop_icons_from_installed_apps
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]

SHIPPED = "Test Shipped App Icon"


@contextmanager
def empty_desktop():
	"""No icons for the length of the test, and the site's own put back afterwards."""
	frappe.db.savepoint("empty_desktop")
	try:
		frappe.db.delete("Desktop Icon")
		yield
	finally:
		frappe.db.rollback(save_point="empty_desktop")


class IntegrationTestDesktopIcon(IntegrationTestCase):
	"""An app's own icon is found by its `app`, not by a label that has to equal `app_title`.

	Apps ship App icons under labels of their own (frappe ships "Framework" with the title
	"Frappe Framework"), and an icon of another type can hold the title as its name (India
	Compliance ships a Folder called "India Compliance").
	"""

	def make_icon(self, label: str, **kwargs):
		return frappe.get_doc(
			{"doctype": "Desktop Icon", "label": label, "link_type": "External", **kwargs}
		).insert()

	def app_icons(self, app: str = "frappe") -> list[str]:
		return frappe.get_all("Desktop Icon", filters={"icon_type": "App", "app": app}, pluck="name")

	def test_an_app_shipping_its_own_icon_is_not_given_a_second(self):
		with empty_desktop():
			self.make_icon(SHIPPED, icon_type="App", app="frappe")

			create_desktop_icons_from_installed_apps()

			self.assertEqual(self.app_icons(), [SHIPPED])

	def test_an_app_title_held_by_another_icon_does_not_abort_the_seeding(self):
		app_title = frappe.get_hooks("app_title", app_name="frappe")[0]
		with empty_desktop():
			self.make_icon(app_title, icon_type="Folder", app="frappe")

			create_desktop_icons_from_installed_apps()

			self.assertEqual(frappe.db.get_value("Desktop Icon", app_title, "icon_type"), "Folder")
			self.assertEqual(self.app_icons(), [])
