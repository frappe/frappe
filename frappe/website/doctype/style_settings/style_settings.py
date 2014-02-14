# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cint, cstr
from frappe import _

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		"""make custom css"""
		self.validate_colors()
		
	def validate_colors(self):
		if (self.doc.page_background or self.doc.page_text) and \
			self.doc.page_background==self.doc.page_text:
				frappe.msgprint(_("Page text and background is same color. Please change."),
					raise_exception=1)

		if (self.doc.top_bar_background or self.doc.top_bar_foreground) and \
			self.doc.top_bar_background==self.doc.top_bar_foreground:
				frappe.msgprint(_("Top Bar text and background is same color. Please change."),
					raise_exception=1)
	
	def on_update(self):
		"""clear cache"""
		from frappe.sessions import clear_cache
		clear_cache('Guest')

		from frappe.website.render import clear_cache
		clear_cache()
