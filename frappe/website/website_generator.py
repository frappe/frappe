# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import quoted
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.website.utils import cleanup_page_name, get_home_page
from frappe.website.render import clear_cache
from frappe.modules import get_module_name
from frappe.website.router import get_page_context_from_template, get_page_context

class WebsiteGenerator(Document):
	website = frappe._dict(
		page_title_field = "name"
	)

	def autoname(self):
		if not self.name and self.meta.autoname != "hash":
			self.name = self.scrub(self.get(self.website.page_title_field or "title"))

	def onload(self):
		self.get("__onload").update({
			"is_website_generator": True,
			"published": self.is_website_published()
		})

	def validate(self):
		if self.is_website_published() and not self.route:
			self.route = self.make_route()

		if self.route:
			self.route = self.route.strip('/.')

	def make_route(self):
		return self.scrub(self.get(self.website.page_title_field or "name"))

	def on_update(self):
		clear_cache(self.route)
		if getattr(self, "save_versions", False):
			frappe.add_version(self)

	def clear_cache(self):
		clear_cache(self.route)

	def scrub(self, text):
		return quoted(cleanup_page_name(text).replace('_', '-'))

	def get_parents(self, context):
		'''Return breadcrumbs'''
		pass

	def on_trash(self):
		self.clear_cache()

	def is_website_published(self):
		"""Return true if published in website"""
		if self.website.condition_field:
			return self.get(self.website.condition_field) and True or False
		else:
			return True

	def get_page_info(self):
		route = frappe._dict()
		route.update({
			"doc": self,
			"page_or_generator": "Generator",
			"ref_doctype":self.doctype,
			"idx": self.idx,
			"docname": self.name,
			"controller": get_module_name(self.doctype, self.meta.module),
		})

		route.update(self.website)

		if not route.page_title:
			route.page_title = self.get(self.website.page_title_field or "name")

		return route
