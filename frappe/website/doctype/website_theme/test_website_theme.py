# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.website_theme.website_theme import (
	after_migrate,
	get_active_theme,
	get_scss_paths,
)


@contextmanager
def website_theme_fixture(**theme):
	test_theme = "test-theme"

	frappe.delete_doc_if_exists("Website Theme", test_theme)
	theme = frappe.get_doc(doctype="Website Theme", theme=test_theme, **theme)
	theme.insert()
	yield theme
	frappe.db.set_single_value("Website Settings", "website_theme", "Standard")
	theme.delete()


class TestWebsiteTheme(FrappeTestCase):
	def test_website_theme(self):
		with website_theme_fixture(
			google_font="Inter",
			custom_scss="body { font-size: 16.5px; }",  # this will get minified!
		) as theme:

			theme_path = frappe.get_site_path("public", theme.theme_url[1:])
			with open(theme_path) as theme_file:
				css = theme_file.read()

			self.assertTrue("body{font-size:16.5px}" in css)
			self.assertTrue("fonts.googleapis.com" in css)

	def test_get_scss_paths(self):
		self.assertIn("frappe/public/scss/website.bundle", get_scss_paths())

	def test_imports_to_ignore(self):
		with website_theme_fixture(ignored_apps=[{"app": "frappe"}]) as theme:
			self.assertTrue('@import "frappe/public/scss/website"' not in theme.theme_scss)

	def test_after_migrate_hook(self):
		with website_theme_fixture(google_font="Inter") as theme:
			theme.set_as_default()
			before = get_active_theme().theme_url
			after_migrate()
			after = get_active_theme().theme_url
			self.assertNotEqual(before, after)
