# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache

class BlogCategory(WebsiteGenerator):
	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.name = self.category_name

	def on_update(self):
		clear_cache()

	def validate(self):
		if not self.route:
			self.route = 'blog/' + self.scrub(self.name)
		super(BlogCategory, self).validate()
