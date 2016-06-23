from __future__ import unicode_literals
import unittest
import frappe
from frappe.website.router import resolve_route

test_records = frappe.get_test_records('Web Page')

class TestWebPage(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("delete from `tabWeb Page`")
		for t in test_records:
			frappe.get_doc(t).insert()

	def test_check_sitemap(self):
		resolve_route("test-web-page-1")
		resolve_route("test-web-page-1/test-web-page-2")
		resolve_route("test-web-page-1/test-web-page-3")