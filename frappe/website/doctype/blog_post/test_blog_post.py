# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe
import unittest

from frappe.utils import set_request
from frappe.website.render import render
from frappe.utils import random_string

class TestBlogPost(unittest.TestCase):
	def test_generator_view(self):
		pages = frappe.get_all('Blog Post', fields=['name', 'route'],
			filters={'published': 1, 'route': ('!=', '')}, limit =1)

		set_request(path=pages[0].route)
		response = render()

		self.assertTrue(response.status_code, 200)

		html = response.get_data().decode()
		self.assertTrue('<article class="blog-content" itemscope itemtype="http://schema.org/BlogPosting">' in html)

	def test_generator_not_found(self):
		pages = frappe.get_all('Blog Post', fields=['name', 'route'],
			filters={'published': 0}, limit =1)

		frappe.db.set_value('Blog Post', pages[0].name, 'route', 'test-route-000')

		set_request(path='test-route-000')
		response = render()

		self.assertTrue(response.status_code, 404)

def make_test_blog():
	if not frappe.db.exists('Blog Category', 'Test Blog Category'):
		frappe.get_doc(dict(
			doctype = 'Blog Category',
			category_name = 'Test Blog Category',
			title='Test Blog Category')).insert()
	if not frappe.db.exists('Blogger', 'test-blogger'):
		frappe.get_doc(dict(
			doctype = 'Blogger',
			short_name='test-blogger',
			full_name='Test Blogger')).insert()
	test_blog = frappe.get_doc(dict(
		doctype = 'Blog Post',
		blog_category = 'Test Blog Category',
		blogger = 'test-blogger',
		title = random_string(20),
		route = random_string(20),
		content = random_string(20),
		published = 1
	)).insert()

	return test_blog

