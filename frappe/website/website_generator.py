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
		self.get("__onload").website_route = frappe.db.get_value("Website Route",
			{"ref_doctype": self.doctype, "docname": self.name})

	def get_parent_website_route(self):
		return self.get("parent_website_route", "")

	def on_update(self):
		self.update_sitemap()
		if getattr(self, "save_versions", False):
			frappe.add_version(self)

	def after_rename(self, olddn, newdn, merge):
		frappe.db.sql("""update `tabWebsite Route`
			set docname=%s where ref_doctype=%s and docname=%s""",
			(newdn, self.doctype, olddn))

		if merge:
			remove_sitemap(ref_doctype=self.doctype, docname=olddn)

	def on_trash(self):
		remove_sitemap(ref_doctype=self.doctype, docname=self.name)

	def update_sitemap(self):
		remove_sitemap(ref_doctype=self.doctype, docname=self.name)

		# check if "condtion_field" property is okay
		self.controller_module = load_doctype_module(self.doctype)
		if hasattr(self.controller_module, "condition_field"):
			if not self.get(self.controller_module.condition_field):
				return

		self.add_or_update_sitemap()

	def add_or_update_sitemap(self):
		page_name = self.get_page_name()

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
			"page_name": page_name,
			"controller": get_module_name(self.doctype, self.meta.module),
			"template": self.controller_module.template,
			"lastmod": lastmod,
			"parent_website_route": self.get_parent_website_route(),
			"page_title": self.get_page_title(),
			"public_read": 1 if not getattr(self, "no_sidebar", None) else 0
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
