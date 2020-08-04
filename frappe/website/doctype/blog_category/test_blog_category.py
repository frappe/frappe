# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe

class TestBlogCategory(unittest.TestCase):
	def test_route(self):
		cat = frappe.new_doc("Blog Categroy", {
			"title": "_Yet Another Category",
			"category_name": "test-category-yet-another-category",
		})
		cat.insert()
		self.assertEqual(cat.route, 'blog/test-category-yet-another-category')
