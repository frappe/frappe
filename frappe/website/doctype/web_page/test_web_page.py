from __future__ import unicode_literals
import unittest
import frappe

test_records = [
	[{
		"doctype": "Web Page",
		"title": "Test Web Page 1",
		"main_section": "Test Content 1",
		"published": 1
	}],
	[{
		"doctype": "Web Page",
		"title": "Test Web Page 2",
		"main_section": "Test Content 2",
		"published": 1,
		"parent_website_route": "test-web-page-1"
	}],
	[{
		"doctype": "Web Page",
		"title": "Test Web Page 3",
		"main_section": "Test Content 3",
		"published": 1,
		"parent_website_route": "test-web-page-1"
	}],
	[{
		"doctype": "Web Page",
		"title": "Test Web Page 4",
		"main_section": "Test Content 4",
		"published": 1,
	}],
]

def TestWebPage(unittest.TestCase):
	def check_sitemap(self):
		self.assertEquals(frappe.conn.get_value("Website Route", ""))