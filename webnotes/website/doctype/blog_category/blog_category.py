# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator, cleanup_page_name, clear_cache

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
	
	def get_page_title(self):
		return self.doc.title
		
	def on_update(self):
		WebsiteGenerator.on_update(self)

		from webnotes.webutils import clear_cache
		clear_cache()
		