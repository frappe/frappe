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
				self.add_section(context, item)
			else:
				self.add_item(context, item)

			self.add_css_class(context, item)

		return context

	def add_section(self, context, item):
		item.elements = []
		context.sections.append(item)

		if item.section_intro:
			item.section_intro = markdown(item.section_intro)

	def add_item(self, context, item):
		if item.hide:
			return

		if item.web_content_type == 'Markdown':
			item.web_content_html = markdown(item.web_content_markdown)

		if item.title:
			item.element_id = frappe.scrub(item.title)

		context.sections[-1].elements.append(item)

	def add_css_class(self, context, item):
		# add css class definitions selected by the user
		if item.element_class and not item.hide:
			css, is_dynamic = frappe.db.get_value('CSS Class', item.element_class, ['css', 'is_dynamic'])
			if is_dynamic:
				css = frappe.render_template(css, self.get_theme())
			context.css_rules.append(css)

	def render_content(self):
		# webview can be rendered as an object (see footer)
		return frappe.render_template("frappe/website/doctype/web_view/templates/web_view_content.html", self.get_context(self.as_dict()))

	def get_theme(self):
		# get theme properties
		if not hasattr(self, '_theme'):
			default_theme = frappe.db.get_value("Website Settings", "Website Settings", "website_theme")
			self._theme = frappe.get_value('Website Theme', default_theme, '*')
		return self._theme

	def add_default_section(self, context):
		# add a default section if not added
		context.sections.append(frappe._dict(
			element_type='Section',
			section_type='List',
			title='Default Section',
			elements=[]
		))
