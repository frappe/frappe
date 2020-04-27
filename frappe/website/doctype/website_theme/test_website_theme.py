# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import os
import frappe
import unittest

test_records = frappe.get_test_records('Website Theme')

class TestWebsiteTheme(unittest.TestCase):
	def test_website_theme(self):
		if os.environ.get('CI'):
			# no node-sass on travis (?)
			return

		frappe.delete_doc_if_exists('Website Theme', 'test-theme')
		theme = frappe.get_doc(dict(
			doctype = 'Website Theme',
			theme = 'test-theme',
			google_font = 'Inter',
			custom_scss = 'body { font-size: 16.5px; }'
		)).insert()

		with open(theme.theme_url[1:]) as f:
			css = f.read()

		self.assertTrue(theme.custom_scss in css)
		self.assertTrue('fonts.googleapis.com' in css)

