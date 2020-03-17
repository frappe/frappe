# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import markdown
import frappe

class WebView(WebsiteGenerator):
	def get_context(self, context):
		# group items into sections
		context.sections = []
		context.css_rules = []
		for item in self.items:
			if not context.sections and item.element_type!='Section':
				self.add_default_section(context)

			if item.element_type=='Section':
				item.elements = []
				context.sections.append(item)

				if item.section_intro:
					item.section_intro = markdown(item.section_intro)

			else:
				if item.hide:
					continue

				if item.web_content_type == 'Markdown':
					item.web_content_html = markdown(item.web_content_markdown)

				if item.title:
					item.element_id = frappe.scrub(item.title)

				context.sections[-1].elements.append(item)

			if item.element_class:
				css, is_dynamic = frappe.db.get_value('CSS Class', item.element_class, ['css', 'is_dynamic'])
				if is_dynamic:
					css = frappe.render_template(css, self.get_theme())
				context.css_rules.append(css)

	def get_theme(self):
		# get theme properties
		if not hasattr(self, '_theme'):
			default_theme = frappe.db.get_value("Website Settings", "Website Settings", "website_theme")
			self._theme = frappe.get_value('Website Theme', default_theme, '*')
		return self._theme

	def add_default_section(self, context):
		# add a default section if not added
		context.section.append(dict(
			element_type='Section',
			section_type='List',
			title='Default Section',
			elements=[]
		))
