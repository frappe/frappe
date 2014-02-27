# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.doc.name = self.doc.category_name
	
	def get_page_title(self):
		return self.doc.title or self.doc.name
		
	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache()
