# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.website.utils import cleanup_page_name
from frappe.utils import now
from frappe.modules import get_module_name, load_doctype_module

from frappe.website.doctype.website_route.website_route import remove_sitemap

class WebsiteGenerator(Document):
	def autoname(self):
		self.name = self.get_page_name()
		append_number_if_name_exists(self)

	def onload(self):
		self.get("__onload").website_route = self.get_route()

	def get_parent_website_route(self):
		return self.get("parent_website_route", "")

	def validate(self):
		if self.is_condition_field_enabled() and self.meta.get_field("page_name") and not self.page_name:
			self.page_name = self.get_page_name()

	def on_update(self):
		self.update_sitemap()
		if getattr(self, "save_versions", False):
			frappe.add_version(self)

	def get_route(self):
		parent = self.get_parent_website_route()
		return ((parent + "/") if parent else "") + self.get_page_name()

	def get_route_docname(self, name=None):
		return frappe.db.get_value("Website Route",
			{"ref_doctype":self.doctype, "docname": name or self.name})

	def after_rename(self, olddn, newdn, merge):
		if self.is_condition_field_enabled():
			self.update_route(self.get_route_docname())

	def on_trash(self):
		remove_sitemap(ref_doctype=self.doctype, docname=self.name)

	def is_condition_field_enabled(self):
		self.controller_module = load_doctype_module(self.doctype)
		if hasattr(self.controller_module, "condition_field"):
			return self.get(self.controller_module.condition_field) and True or False
		else:
			return True

	def update_sitemap(self):
		# update route of all descendants
		route_docname = self.get_route_docname()

		if not self.is_condition_field_enabled():
			frappe.delete_doc("Website Route", route_docname, ignore_permissions=True)
			return

		if route_docname:
			self.update_route(route_docname)
		else:
			self.insert_route()

	def update_route(self, route_docname):
		route = frappe.get_doc("Website Route", route_docname)
		if self.get_route() != route_docname:
			route.rename(self.get_page_name(), self.get_parent_website_route())

		if self.is_changed(route):
			route.idx = self.idx
			route.page_title = self.get_page_title()
			self.update_permissions(route)
			route.save(ignore_permissions=True)

	def is_changed(self, route):
		if route.idx != self.idx or route.page_title != self.get_page_title():
			return True
		if self.meta.get_field("public_read"):
			if route.public_read != self.public_read \
				or route.public_write != self.public_write:
				return True

		return False

	def insert_route(self):
		if self.modified:
			# for sitemap.xml
			lastmod = frappe.utils.get_datetime(self.modified).strftime("%Y-%m-%d")
		else:
			lastmod = now()

		route = frappe.new_doc("Website Route")
		route.update({
			"page_or_generator": "Generator",
			"ref_doctype":self.doctype,
			"idx": self.idx,
			"docname": self.name,
			"page_name": self.get_page_name(),
			"controller": get_module_name(self.doctype, self.meta.module),
			"template": self.controller_module.template,
			"lastmod": lastmod,
			"parent_website_route": self.get_parent_website_route(),
			"page_title": self.get_page_title()
		})

		self.update_permissions(route)
		route.ignore_links = True
		route.insert(ignore_permissions=True)

	def update_permissions(self, route):
		if self.meta.get_field("public_read"):
			route.public_read = self.public_read
			route.public_write = self.public_write
		else:
			route.public_read = 1

	def get_page_name(self):
		return self.get_or_make_page_name()

	def get_page_name_field(self):
		return self.page_name_field if hasattr(self, "page_name_field") else "page_name"

	def get_or_make_page_name(self):
		page_name = self.get(self.get_page_name_field())
		if not page_name:
			page_name = cleanup_page_name(self.get_page_title())
			if self.is_new():
				self.set(self.get_page_name_field(), page_name)

		return page_name

	def get_page_title(self):
		return self.get("title") or (self.name.replace("-", " ").replace("_", " ").title())
