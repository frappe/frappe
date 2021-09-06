# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.website.website_generator import WebsiteGenerator
from frappe.website.utils import clear_cache

class BlogCategory(WebsiteGenerator):
	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.name = self.scrub(self.title)

	def on_update(self):
		clear_cache()

	def set_route(self):
		# Override blog route since it has to been templated
		self.route = 'blog/' + self.name
