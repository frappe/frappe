from __future__ import unicode_literals

import frappe, unittest
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

from frappe.website import render

def set_request(**kwargs):
	builder = EnvironBuilder(**kwargs)
	frappe.local.request = Request(builder.get_environ())

def get_html_for_route(route):
	set_request(method='GET', path=route)
	response = render.render()
	html = frappe.safe_decode(response.get_data())
	return html

class TestWebsite(unittest.TestCase):

	def test_page_load(self):
		frappe.set_user('Guest')
		set_request(method='POST', path='login')
		response = render.render()

		self.assertEquals(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue('/* login-css */' in html)
		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)
		frappe.set_user('Administrator')

	def test_redirect(self):
		import frappe.hooks
		frappe.hooks.website_redirects = [
			dict(source=r'/testfrom', target=r'://testto1'),
			dict(source=r'/testfromregex.*', target=r'://testto2'),
			dict(source=r'/testsub/(.*)', target=r'://testto3/\1')
		]

		website_settings = frappe.get_doc('Website Settings')
		website_settings.append('route_redirects', {
			'source': '/testsource',
			'target': '/testtarget'
		})
		website_settings.save()

		frappe.cache().delete_key('app_hooks')
		frappe.cache().delete_key('website_redirects')

		set_request(method='GET', path='/testfrom')
		response = render.render()
		self.assertEquals(response.status_code, 301)
		self.assertEquals(response.headers.get('Location'), r'://testto1')

		set_request(method='GET', path='/testfromregex/test')
		response = render.render()
		self.assertEquals(response.status_code, 301)
		self.assertEquals(response.headers.get('Location'), r'://testto2')

		set_request(method='GET', path='/testsub/me')
		response = render.render()
		self.assertEquals(response.status_code, 301)
		self.assertEquals(response.headers.get('Location'), r'://testto3/me')

		set_request(method='GET', path='/test404')
		response = render.render()
		self.assertEquals(response.status_code, 404)

		set_request(method='GET', path='/testsource')
		response = render.render()
		self.assertEquals(response.status_code, 301)
		self.assertEquals(response.headers.get('Location'), '/testtarget')

		delattr(frappe.hooks, 'website_redirects')
		frappe.cache().delete_key('app_hooks')

