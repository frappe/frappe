import unittest

import frappe
from frappe.utils import set_request
from frappe.website.serve import get_response, get_response_content
from frappe.website.utils import (build_response, clear_website_cache, get_home_page)


class TestWebsite(unittest.TestCase):
	def setUp(self):
		frappe.set_user('Guest')

	def tearDown(self):
		frappe.set_user('Administrator')

	def test_home_page(self):
		frappe.set_user('Administrator')
		# test home page via role
		user = frappe.get_doc(dict(
			doctype='User',
			email='test-user-for-home-page@example.com',
			first_name='test')).insert(ignore_if_duplicate=True)

		role = frappe.get_doc(dict(
			doctype = 'Role',
			role_name = 'home-page-test',
			desk_access = 0,
		)).insert(ignore_if_duplicate=True)

		user.add_roles(role.name)
		user.save()

		frappe.db.set_value('Role', 'home-page-test', 'home_page', 'home-page-test')
		frappe.set_user('test-user-for-home-page@example.com')
		self.assertEqual(get_home_page(), 'home-page-test')

		frappe.set_user('Administrator')
		frappe.db.set_value('Role', 'home-page-test', 'home_page', '')

		# home page via portal settings
		frappe.db.set_value('Portal Settings', None, 'default_portal_home', 'test-portal-home')

		frappe.set_user('test-user-for-home-page@example.com')
		frappe.cache().hdel('home_page', frappe.session.user)
		self.assertEqual(get_home_page(), 'test-portal-home')

		frappe.db.set_value("Portal Settings", None, "default_portal_home", '')
		clear_website_cache()

		# home page via website settings
		frappe.db.set_value("Website Settings", None, "home_page", 'contact')
		self.assertEqual(get_home_page(), 'contact')

		frappe.db.set_value("Website Settings", None, "home_page", None)
		clear_website_cache()

		# fallback homepage
		self.assertEqual(get_home_page(), 'me')

		# fallback homepage for guest
		frappe.set_user('Guest')
		self.assertEqual(get_home_page(), 'login')
		frappe.set_user('Administrator')

		# test homepage via hooks
		clear_website_cache()
		set_home_page_hook('get_website_user_home_page', 'frappe.www._test._test_home_page.get_website_user_home_page')
		self.assertEqual(get_home_page(), '_test/_test_folder')

		clear_website_cache()
		set_home_page_hook('website_user_home_page', 'login')
		self.assertEqual(get_home_page(), 'login')

		clear_website_cache()
		set_home_page_hook('home_page', 'about')
		self.assertEqual(get_home_page(), 'about')

		clear_website_cache()
		set_home_page_hook('role_home_page', {'home-page-test': 'home-page-test'})
		self.assertEqual(get_home_page(), 'home-page-test')


	def test_page_load(self):
		set_request(method='POST', path='login')
		response = get_response()

		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)

	def test_static_page(self):
		set_request(method='GET', path='/_test/static-file-test.png')
		response = get_response()
		self.assertEqual(response.status_code, 200)

	def test_error_page(self):
		set_request(method='GET', path='/_test/problematic_page')
		response = get_response()
		self.assertEqual(response.status_code, 500)

	def test_login(self):
		set_request(method='GET', path='/login')
		response = get_response()
		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue('// login.js' in html)
		self.assertTrue('<!-- login.html -->' in html)

	def test_app(self):
		frappe.set_user('Administrator')
		set_request(method='GET', path='/app')
		response = get_response()
		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())
		self.assertTrue('window.app = true;' in html)
		frappe.local.session_obj = None

	def test_not_found(self):
		set_request(method='GET', path='/_test/missing')
		response = get_response()
		self.assertEqual(response.status_code, 404)


	def test_redirect(self):
		import frappe.hooks
		frappe.set_user('Administrator')

		frappe.hooks.website_redirects = [
			dict(source=r'/testfrom', target=r'://testto1'),
			dict(source=r'/testfromregex.*', target=r'://testto2'),
			dict(source=r'/testsub/(.*)', target=r'://testto3/\1'),
			dict(source=r'/courses/course\?course=(.*)', target=r'/courses/\1', match_with_query_string=True),
		]

		website_settings = frappe.get_doc('Website Settings')
		website_settings.append('route_redirects', {
			'source': '/testsource',
			'target': '/testtarget'
		})
		website_settings.save()

		set_request(method='GET', path='/testfrom')
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get('Location'), r'://testto1')

		set_request(method='GET', path='/testfromregex/test')
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get('Location'), r'://testto2')

		set_request(method='GET', path='/testsub/me')
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get('Location'), r'://testto3/me')

		set_request(method='GET', path='/test404')
		response = get_response()
		self.assertEqual(response.status_code, 404)

		set_request(method='GET', path='/testsource')
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get('Location'), '/testtarget')

		set_request(method='GET', path='/courses/course?course=data')
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get('Location'), '/courses/data')

		delattr(frappe.hooks, 'website_redirects')
		frappe.cache().delete_key('app_hooks')

	def test_custom_page_renderer(self):
		import frappe.hooks
		frappe.hooks.page_renderer = ['frappe.tests.test_website.CustomPageRenderer']
		frappe.cache().delete_key('app_hooks')
		set_request(method='GET', path='/custom')
		response = get_response()
		self.assertEqual(response.status_code, 3984)

		set_request(method='GET', path='/new')
		content = get_response_content()
		self.assertIn("<div>Custom Page Response</div>", content)

		set_request(method='GET', path='/random')
		response = get_response()
		self.assertEqual(response.status_code, 404)

		delattr(frappe.hooks, 'page_renderer')
		frappe.cache().delete_key('app_hooks')

	def test_printview_page(self):
		content = get_response_content('/Language/en')
		self.assertIn('<div class="print-format">', content)
		self.assertIn('<div>Language</div>', content)


def set_home_page_hook(key, value):
	from frappe import hooks
	# reset home_page hooks
	for hook in ('get_website_user_home_page','website_user_home_page','role_home_page','home_page'):
		if hasattr(hooks, hook):
			delattr(hooks, hook)

	setattr(hooks, key, value)
	frappe.cache().delete_key('app_hooks')

class CustomPageRenderer():
	def __init__(self, path, status_code=None):
		self.path = path
		# custom status code
		self.status_code = 3984

	def can_render(self):
		if self.path in ('new', 'custom'):
			return True

	def render(self):
		return build_response(self.path, """<div>Custom Page Response</div>""", self.status_code)
