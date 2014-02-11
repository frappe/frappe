# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator
from webnotes.templates.generators.website_group import clear_cache
from webnotes.model.doc import make_autoname

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def autoname(self):
		self.doc.name = make_autoname("Website-Group-.######")
		
	def get_page_title(self):
		return self.doc.group_title
	
	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache(website_group=self.doc.name)
		
	def after_insert(self):
		clear_cache(path=self.doc.parent_website_sitemap)