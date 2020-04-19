# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.website.doctype.web_template.web_template import get_rendered_template


class WebPageBlock(Document):
	def render(self):
		values = frappe.parse_json(self.web_template_values)
		rendered_html = get_rendered_template(self.web_template, values)
		return rendered_html


def render_web_page_blocks(blocks):
	for block in blocks:
		context = frappe._dict()
		context.dark_theme = block.dark_theme
		values = frappe.parse_json(block.web_template_values)
		context.update(values)
		rendered_html = get_rendered_template(block.web_template, context)
		section = frappe._dict(block.as_dict())
		section.rendered_html = rendered_html
		sections.append(section)
