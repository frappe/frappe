# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import cint

from frappe.model.document import Document


class PrintSettings(Document):
	def validate(self):
		if self.pdf_page_size == "Custom" and not (
			self.pdf_page_height and self.pdf_page_width
		):
			frappe.throw(_("Page height and width cannot be zero"))

	def on_update(self):
		frappe.clear_cache()

