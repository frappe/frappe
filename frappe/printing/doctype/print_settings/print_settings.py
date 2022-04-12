# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class PrintSettings(Document):
	def validate(self):
		if self.pdf_page_size == "Custom" and not (self.pdf_page_height and self.pdf_page_width):
			frappe.throw(_("Page height and width cannot be zero"))

	def on_update(self):
		frappe.clear_cache()


@frappe.whitelist()
def is_print_server_enabled():
	if not hasattr(frappe.local, "enable_print_server"):
		frappe.local.enable_print_server = cint(
			frappe.db.get_single_value("Print Settings", "enable_print_server")
		)

	return frappe.local.enable_print_server
