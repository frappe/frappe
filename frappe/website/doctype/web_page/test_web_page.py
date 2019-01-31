from __future__ import unicode_literals
import unittest
import frappe
from frappe.website.router import resolve_route
import frappe.website.render
from frappe.tests import set_request

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

	def test_base_template(self):
		set_request(method='GET', path = '/_test/_test_custom_base.html')

		response = frappe.website.render.render()

		# assert the text in base template is rendered
		self.assertTrue('<h1>This is for testing</h1>' in frappe.as_unicode(response.data))

		# assert template block rendered
		self.assertTrue('<p>Test content</p>' in frappe.as_unicode(response.data))


