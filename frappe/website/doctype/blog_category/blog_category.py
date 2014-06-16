# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache

template = "templates/generators/blog_category.html"
no_cache = True

class BlogCategory(WebsiteGenerator):
	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.name = self.category_name

	def get_page_title(self):
		return self.title or self.name

	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache()
