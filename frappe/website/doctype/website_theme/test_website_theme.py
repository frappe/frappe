# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import os
import frappe
import unittest
from .website_theme import get_scss_paths

class TestWebsiteTheme(unittest.TestCase):

	def test_website_theme(self):
		frappe.delete_doc_if_exists('Website Theme', 'test-theme')
		theme = frappe.get_doc(dict(
			doctype='Website Theme',
			theme='test-theme',
			google_font='Inter',
			custom_scss='body { font-size: 16.5px; }' # this will get minified!
		)).insert()

		theme_path = frappe.get_site_path('public', theme.theme_url[1:])
		with open(theme_path) as theme_file:
			css = theme_file.read()

		self.assertTrue('body{font-size:16.5px}' in css)
		self.assertTrue('fonts.googleapis.com' in css)

	def test_get_scss_paths(self):
		self.assertIn('frappe/public/scss/website', get_scss_paths())

	def test_imports_to_ignore(self):
		frappe.delete_doc_if_exists('Website Theme', 'test-theme')
		theme = frappe.get_doc(dict(
			doctype='Website Theme',
			theme='test-theme',
			ignored_apps=[{ 'app': 'frappe'}]
		)).insert()

		self.assertTrue('@import "frappe/public/scss/website"' not in theme.theme_scss)
