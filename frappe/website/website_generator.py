# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.controller import DocListController
from frappe.website.utils import cleanup_page_name

from frappe.website.doctype.website_sitemap.website_sitemap import add_to_sitemap, update_sitemap, remove_sitemap

def call_website_generator(bean, method, *args, **kwargs):
	getattr(WebsiteGenerator(bean.doc, bean.doclist), method)(*args, **kwargs)

class WebsiteGenerator(DocListController):
	def autoname(self):
		self.doc.name = cleanup_page_name(self.get_page_title())

	def set_page_name(self):
		"""set page name based on parent page_name and title"""
		page_name = cleanup_page_name(self.get_page_title())

		if self.doc.is_new():
			self.doc.fields[self._website_config.page_name_field] = page_name
		else:
			frappe.conn.set(self.doc, self._website_config.page_name_field, page_name)
			
		return page_name

	def get_parent_website_sitemap(self):
		return self.doc.parent_website_sitemap

	def setup_generator(self):
		self._website_config = frappe.conn.get_values("Website Sitemap Config", 
			{"ref_doctype": self.doc.doctype}, "*")[0]

	def on_update(self):
		self.update_sitemap()
		
	def after_rename(self, olddn, newdn, merge):
		frappe.conn.sql("""update `tabWebsite Sitemap`
			set docname=%s where ref_doctype=%s and docname=%s""", (newdn, self.doc.doctype, olddn))
		
		if merge:
			self.setup_generator()
			remove_sitemap(ref_doctype=self.doc.doctype, docname=olddn)
		
	def on_trash(self):
		self.setup_generator()
		remove_sitemap(ref_doctype=self.doc.doctype, docname=self.doc.name)
		
	def update_sitemap(self):
		self.setup_generator()
		
		if self._website_config.condition_field and \
			not self.doc.fields.get(self._website_config.condition_field):
			# condition field failed, remove and return!
			remove_sitemap(ref_doctype=self.doc.doctype, docname=self.doc.name)
			return
				
		self.add_or_update_sitemap()
		
	def add_or_update_sitemap(self):
		page_name = self.get_page_name()
		
		existing_site_map = frappe.conn.get_value("Website Sitemap", {"ref_doctype": self.doc.doctype,
			"docname": self.doc.name})
						
		opts = frappe._dict({
			"page_or_generator": "Generator",
			"ref_doctype":self.doc.doctype, 
			"idx": self.doc.idx,
			"docname": self.doc.name,
			"page_name": page_name,
			"link_name": self._website_config.name,
			"lastmod": frappe.utils.get_datetime(self.doc.modified).strftime("%Y-%m-%d"),
			"parent_website_sitemap": self.get_parent_website_sitemap(),
			"page_title": self.get_page_title(),
			"public_read": 1 if not self._website_config.no_sidebar else 0
		})

		self.update_permissions(opts)
		
		if existing_site_map:
			idx = update_sitemap(existing_site_map, opts)
		else:
			idx = add_to_sitemap(opts)
			
		if idx!=None and self.doc.idx != idx:
			frappe.conn.set(self.doc, "idx", idx)
	
	def update_permissions(self, opts):
		if self.meta.get_field("public_read"):
			opts.public_read = self.doc.public_read
			opts.public_write = self.doc.public_write
		else:
			opts.public_read = 1
	
	def get_page_name(self):
		page_name = self._get_page_name()
		if not page_name:
			page_name = self.set_page_name()
			
		return self._get_page_name()
		
	def _get_page_name(self):
		if self.meta.has_field(self._website_config.page_name_field):
			return self.doc.fields.get(self._website_config.page_name_field)
		else:
			return cleanup_page_name(self.get_page_title())
		
	def get_page_title(self):
		return self.doc.title or (self.doc.name.replace("-", " ").replace("_", " ").title())
