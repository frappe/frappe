from __future__ import unicode_literals

import frappe, unittest
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

from frappe.utils import cint
from frappe.website import render
from frappe.website.utils import get_website_settings

def set_request(**kwargs):
	builder = EnvironBuilder(**kwargs)
	frappe.local.request = Request(builder.get_environ())

class TestWebsite(unittest.TestCase):

	def test_page_load(self):
		set_request(method='POST', path='login')
		response = render.render()

		self.assertTrue(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue('/* login-css */' in html)
		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)

	def test_redirect(self):
		import frappe.hooks
		frappe.hooks.website_redirects = [
			dict(source='/testfrom', target='://testto1'),
			dict(source='/testfromregex.*', target='://testto2'),
			dict(source='/testsub/(.*)', target='://testto3/\1')
		]
		frappe.cache().delete_key('app_hooks')
		frappe.cache().delete_key('website_redirects')

		set_request(method='GET', path='/testfrom')
		response = render.render()
		self.assertTrue(response.status_code, 301)
		self.assertTrue(response.headers.get('Location'), '://testto1')

		set_request(method='GET', path='/testfromregex/test')
		response = render.render()
		self.assertTrue(response.status_code, 301)
		self.assertTrue(response.headers.get('Location'), '://testto2')

		set_request(method='GET', path='/testsub/me')
		response = render.render()
		self.assertTrue(response.status_code, 301)
		self.assertTrue(response.headers.get('Location'), '://testto3/me')

		set_request(method='GET', path='/test404')
		response = render.render()
		self.assertTrue(response.status_code, 404)

		delattr(frappe.hooks, 'website_redirects')
		frappe.cache().delete_key('app_hooks')

	def test_multi_website(self):
		# Try removing is_default
		site1 = get_website_settings()
		site1.is_default = 0
		self.assertRaises(frappe.ValidationError, site1.save)

		# Create new site, set as default, change homepage
		site2 = frappe.new_doc('Website')
		site2.website_name = 'Test Site 2'
		site2.is_default = 1
		site2.home_page = 'blog'
		site2.save()
		self.assertEqual(cint(frappe.db.get_value('Website', site1.name, 'is_default')), 0)

		# Homepage must be 'blog'
		self.assertEqual(get_website_settings('home_page'), 'blog')

		# Reset defaults
		site1 = frappe.get_doc('Website', site1.name)
		site1.is_default = 1
		site1.save()
		self.assertEqual(get_website_settings('home_page'), site1.home_page)
		