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
		# group components into sections
		if self.content_type=='Components':
			self.build_components(context)

		self.set_metatags(context)
		return context

	def build_components(self, context):
		context.sections = []
		context.css_rules = []
		for component in self.components:
			if not context.sections and component.element_type!='Section':
				self.add_default_section(context)

			if component.element_type=='Section':
				self.add_section(context, component)
			else:
				self.add_component(context, component)

			self.add_css_class(context, component)
			self.add_color(component)
			self.add_missing_semi(component)

		return context

	def add_section(self, context, component):
		component.elements = []
		context.sections.append(component)

		if component.section_intro:
			component.section_intro = markdown(component.section_intro)

	def add_component(self, context, component):
		if component.hide:
			return

		if component.element_type == 'Web View' and component.web_view:
			component.web_content_html = frappe.get_doc('Web View', component.web_view).render_content()

		elif component.web_content_type == 'Markdown':
			component.web_content_html = markdown(component.web_content_markdown)

		if component.title:
			component.element_id = frappe.scrub(component.title)

		context.sections[-1].elements.append(component)

	def add_css_class(self, context, component):
		# add css class definitions selected by the user
		if component.element_class and not component.hide:
			css, is_dynamic = frappe.db.get_value('CSS Class', component.element_class, ['css', 'is_dynamic'])
			if is_dynamic:
				css = frappe.render_template(css, self.get_theme())
			context.css_rules.append(css)

	def add_color(self, component):
		# convert to css color
		if component.background_color and not component.hide:
			component.background_color = frappe.db.get_value('Color',
				component.background_color, 'color', cache=True)

	def add_missing_semi(self, component):
		if component.element_style and not component.element_style.strip().endswith(';'):
			component.element_style = component.element_style.strip() + ';'

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

	def set_metatags(self, context):
		context.metatags = {
			"name": self.meta_title or context.title,
			"description": self.meta_description,
			"image": self.meta_image
		}

