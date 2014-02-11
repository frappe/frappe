# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator, cleanup_page_name
from webnotes.templates.generators.website_group import get_context
from webnotes.model.doc import make_autoname

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def autoname(self):
		self.doc.name = make_autoname("Website-Group-.######")
		
	def get_page_title(self):
		return self.doc.group_title