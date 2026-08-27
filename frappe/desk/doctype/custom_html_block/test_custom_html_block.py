# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.desk.doctype.custom_html_block.custom_html_block import get_custom_blocks_for_user
from frappe.tests.utils import FrappeTestCase


class TestCustomHTMLBlock(FrappeTestCase):
	def test_get_custom_blocks_for_user_accepts_none_filters(self):
		result = get_custom_blocks_for_user(
			doctype="Custom HTML Block",
			txt="",
			searchfield="name",
			start=0,
			page_len=20,
			filters=None,
		)
		self.assertIsInstance(result, (list, tuple))

	def test_get_custom_blocks_for_user_accepts_dict_filters(self):
		result = get_custom_blocks_for_user(
			doctype="Custom HTML Block",
			txt="",
			searchfield="name",
			start=0,
			page_len=20,
			filters={},
		)
		self.assertIsInstance(result, (list, tuple))

	def test_search_link_returns_custom_blocks(self):
		from frappe.desk.search import search_link

		block = frappe.get_doc(
			{
				"doctype": "Custom HTML Block",
				"name": "Test Custom Block",
				"html": "<h2>Test Heading</h2>",
			}
		).insert()
		self.addCleanup(block.delete)

		results = search_link(
			doctype="Custom HTML Block",
			txt="",
			query="frappe.desk.doctype.custom_html_block.custom_html_block.get_custom_blocks_for_user",
		)
		self.assertIn(block.name, [r["value"] for r in results])
