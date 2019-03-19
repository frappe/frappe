from __future__ import unicode_literals

import frappe, unittest
from frappe.tests.test_website import get_html_for_route

class TestSitemap(unittest.TestCase):
	def test_page_load(self):
		xml = get_html_for_route('sitemap.xml')
		self.assertTrue('/about</loc>' in xml)
		self.assertTrue('/contact</loc>' in xml)
		self.assertTrue('/blog/general</loc>' in xml)
