# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe.templates.pages.blog import get_children

class BlogCategory(WebsiteGenerator):
	page_title_field = "title"
	template = "templates/generators/blog_category.html"
	no_cache = True
	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.name = self.category_name

	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache()

	def get_children(self):
		return get_children()

	def validate(self):
		self.parent_website_route = "blog"
		super(BlogCategory, self).validate()
