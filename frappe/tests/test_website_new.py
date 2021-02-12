from __future__ import unicode_literals

import unittest

import frappe
from frappe.website import serve
from frappe.website.utils import get_home_page
from frappe.utils import set_request
class TestWebsite(unittest.TestCase):
	def setUp(self):
		frappe.set_user('Guest')

	def tearDown(self):
		frappe.set_user('Administrator')

	def test_static_page(self):
		set_request(method='GET', path='/_test/static-file-test.png')
		response = serve.StaticPage().get()
		self.assertEquals(response.status_code, 200)

	def test_error_page(self):
		set_request(method='GET', path='/error')
		response = serve.get_response()
		self.assertEquals(response.status_code, 500)

	def test_login(self):
		set_request(method='GET', path='/login')
		response = serve.get_response()
		self.assertEquals(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)

	def test_app(self):
		frappe.set_user('Administrator')
		set_request(method='GET', path='/app')
		response = serve.get_response()
		self.assertEquals(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())
		self.assertTrue('window.app = true;' in html)
		frappe.local.session_obj = None

	def test_not_found(self):
		set_request(method='GET', path='/_test/missing')
		response = serve.get_response()
		self.assertEquals(response.status_code, 404)
