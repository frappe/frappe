# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator, cleanup_page_name
from webnotes.templates.generators.website_group import get_context

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.validate_group_name()
		self.doc.name = self.doc.group_name
		
	def validate(self):
		# TODO use titlecase package
		self.doc.group_title = self.doc.group_title.title()
		self.validate_page_name()
		
	def validate_group_name(self):
		self.doc.group_name = cleanup_page_name(self.doc.group_name or self.doc.group_title)
	
	def validate_page_name(self):
		self.doc.page_name = cleanup_page_name(self.doc.page_name or self.doc.group_name)
		
		if not self.doc.page_name:
			webnotes.throw(_("Page Name is mandatory"), raise_exception=webnotes.MandatoryError)
