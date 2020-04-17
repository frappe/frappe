# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe.website.doctype.web_page.test_web_page import get_page_content

test_dependencies = ['Web Page'] # for test

class TestWebView(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.delete_doc_if_exists('Web View', 'test-web-view')
		frappe.delete_doc_if_exists('CSS Class', 'test-css-class')

		frappe.get_doc(dict(
			doctype = 'CSS Class',
			name = 'test-css-class',
			css = '.test-class { color: red; }'
		)).insert()

		frappe.get_doc(dict(
			doctype = 'Web View',
			title = 'Test Web View',
			route = 'test-web-view',
			published = 1,
			items = [
				dict(
					element_type = 'Section',
					section_type = 'List'
				),
				dict(
					element_type = 'Content',
					web_content_type = 'Markdown',
					web_content_markdown = '## Heading\n\nBody'
				),
				dict(
					element_type = 'Content',
					web_content_type = 'HTML',
					web_content_html = '<div>Here is some HTML</div>'
				),
				dict(
					element_type = 'Section',
					section_type = 'Grid'
				),
				dict(
					element_type = 'Content',
					element_class = 'test-css-class',
					web_content_type = 'Markdown',
					web_content_markdown = 'Column 1'
				),
				dict(
					element_type = 'Content',
					web_content_type = 'Markdown',
					web_content_markdown = 'Column 2'
				),
			]
		)).insert()

	def test_web_view(self):
		html = get_page_content('test-web-view')
		#print(html)
		self.assert_web_view_in_html(html)

	def assert_web_view_in_html(self, html):
		self.assertTrue('<h2 id="heading">Heading</h2>' in html)
		self.assertTrue('<div>Here is some HTML</div>' in html)
		self.assertTrue('Column 1' in html)
		self.assertTrue('Column 2' in html)
		self.assertTrue('.test-class { color: red; }' in html)

	def test_web_view_in_footer(self):
		website_settings = frappe.get_single("Website Settings")
		website_settings.footer_type = 'Web View'
		website_settings.footer_web_view = 'test-web-view'
		website_settings.save()

		html = get_page_content('test-web-page-1')

		website_settings.footer_type = 'Standard'
		website_settings.footer_web_view = ''
		website_settings.save()

		# web view should still come as footer
		self.assert_web_view_in_html(html)

		html_without_footer = get_page_content('test-web-page-1')

		# no more footer
		self.assertFalse('Column 1' in html_without_footer)
