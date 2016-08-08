from __future__ import unicode_literals

import frappe, unittest
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

from frappe.website import render

def set_request(**kwargs):
	builder = EnvironBuilder(**kwargs)
	frappe.local.request = Request(builder.get_environ())

class TestWebsite(unittest.TestCase):

	def test_page_load(self):
		set_request(method='POST', path='login')
		response = render.render()

		self.assertTrue(response.status_code, 200)

		html = response.get_data()

		self.assertTrue('/* login-css */' in html)
		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)
