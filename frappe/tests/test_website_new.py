from __future__ import unicode_literals

import unittest

import frappe
from frappe.website import serve
from frappe.website.utils import get_home_page
from frappe.utils import set_request

class TestWebsite(unittest.TestCase):
	def test_static_page(self):
		set_request(method='GET', path='/_test/static-file-test.png')
		response = serve.StaticPage().get()
		self.assertEquals(response.status_code, 200)

	def test_error_page(self):
		set_request(method='GET', path='/error')
		response = serve.TemplatePage().get()
		self.assertEquals(response.status_code, 200)
		print(response.get_data())
