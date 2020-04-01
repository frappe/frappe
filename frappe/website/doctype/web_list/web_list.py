# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator

class WebList(WebsiteGenerator):
	def get_context(self, context):
		context.data = self.get_data()

	def get_data(self):
		return frappe.get_all(self.reference_doctype,
			fields = [d.fieldname for d in self.columns], as_list = True, limit=20)
