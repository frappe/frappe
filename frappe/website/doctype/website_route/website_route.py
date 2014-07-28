# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

sitemap_fields = ("page_name", "ref_doctype", "docname", "page_or_generator", "idx",
	"lastmod", "parent_website_route", "public_read", "public_write", "page_title")

class WebsiteRoute(NestedSet):
	nsm_parent_field = "parent_website_route"

	def autoname(self):
		self.name = self.get_url()

	def get_url(self):
		url = self.page_name
		if self.parent_website_route:
			url = self.parent_website_route + "/" + url
		return url

	def validate(self):
		if not frappe.flags.in_sync_website:
			self.make_private_if_parent_is_private()

	def on_update(self):
		if self.get_url() != self.name:
			self.rename()
		if not frappe.flags.in_sync_website:
			NestedSet.on_update(self)
		self.clear_cache()

	def rename(self, new_page_name=None, new_parent_website_route=None):
		self.old_name = self.name
		self.old_parent_website_route = self.parent_website_route

		# get new route
		if new_page_name != None:
			self.page_name = new_page_name
		if new_parent_website_route != None:
			self.parent_website_route = new_parent_website_route
		self.name = self.get_url()

		# update values (don't run triggers)
		frappe.db.sql("""update `tabWebsite Route` set
			name=%s, page_name=%s, parent_website_route=%s where name=%s""",
				(self.name, self.page_name, self.parent_website_route, self.old_name))

		self.rename_links()
		self.rename_descendants()
		self.clear_cache(self.old_name)
		self.clear_cache(self.old_parent_website_route)
		self.clear_cache(self.parent_website_route)

	def rename_links(self):
		for doctype in frappe.db.sql_list("""select parent from tabDocField
			where fieldtype='Link'
				and fieldname='parent_website_route'
				and options='Website Route'
				and parent!='Website Route'"""):
			for name in frappe.db.sql_list("""select name from `tab{}`
				where parent_website_route=%s""".format(doctype), self.old_name):
				frappe.db.set_value(doctype, name, "parent_website_route", self.name)

	def rename_descendants(self):
		# rename children
		for name in frappe.db.sql_list("""select name from `tabWebsite Route`
			where parent_website_route=%s""", self.old_name):
			child = frappe.get_doc("Website Route", name)
			child.parent_website_route = self.name
			child.save()

	def make_private_if_parent_is_private(self):
		if self.parent_website_route:
			parent_pubic_read = frappe.db.get_value("Website Route", self.parent_website_route,
				"public_read")

			if not parent_pubic_read:
				self.public_read = self.public_write = 0

	def on_trash(self):
		# remove website sitemap permissions
		to_remove = frappe.db.sql_list("""select name from `tabWebsite Route Permission`
			where website_route=%s""", (self.name,))
		frappe.delete_doc("Website Route Permission", to_remove, ignore_permissions=True)
		self.clear_cache()

	def clear_cache(self, name=None):
		from frappe.website.render import clear_cache
		if name:
			clear_cache(name)
		else:
			if self.parent_website_route:
				clear_cache(self.parent_website_route)

			clear_cache(self.name)

def remove_sitemap(page_name=None, ref_doctype=None, docname=None):
	if page_name:
		frappe.delete_doc("Website Route", page_name, ignore_permissions=True, force=True)
	elif ref_doctype and docname:
		frappe.delete_doc("Website Route", frappe.db.sql_list("""select name from `tabWebsite Route`
			where ref_doctype=%s and docname=%s""", (ref_doctype, docname)), ignore_permissions=True, force=True)
