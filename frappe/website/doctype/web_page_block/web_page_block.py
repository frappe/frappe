# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.website.doctype.web_template.web_template import get_rendered_template


class WebPageBlock(Document):
	def render(self):
		values = self.web_template_values or '{}'
		values = frappe.parse_json(values)
		rendered_html = get_rendered_template(self.web_template, values)
		return rendered_html
