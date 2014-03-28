# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.templates.generators.website_group import clear_cache
from frappe.model.naming import make_autoname

class WebsiteGroup(WebsiteGenerator):
		
	def get_page_title(self):
		return self.group_title
	
	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache(website_group=self.name)
		
	def after_insert(self):
		clear_cache(path=self.parent_website_route)
