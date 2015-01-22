# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cint, cstr
from frappe import _

from frappe.model.document import Document

class StyleSettings(Document):

	def validate(self):
		"""make custom css"""
		self.validate_colors()

	def validate_colors(self):
		if (self.top_bar_background or self.top_bar_foreground) and \
			self.top_bar_background==self.top_bar_foreground:
				frappe.msgprint(_("Top Bar text and background is same color. Please change."),
					raise_exception=1)

	def on_update(self):
		"""clear cache"""
		from frappe.sessions import clear_cache
		clear_cache('Guest')

		from frappe.website.render import clear_cache
		clear_cache()
