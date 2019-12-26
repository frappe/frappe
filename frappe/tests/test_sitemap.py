from __future__ import unicode_literals

import frappe, unittest
from frappe.tests.test_website import get_html_for_route

class TestSitemap(unittest.TestCase):
	def test_sitemap(self):
		blogs = frappe.db.get_all('Blog Post', {'published': 1}, ['route'], limit=1)
		xml = get_html_for_route('sitemap.xml')
		self.assertTrue('/about</loc>' in xml)
		self.assertTrue('/contact</loc>' in xml)
		self.assertTrue(blogs[0].route in xml)
