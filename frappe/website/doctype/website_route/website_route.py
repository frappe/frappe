# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
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
		if self.get_url() != self.name:
			self.rename()
		self.check_if_page_name_is_unique()
		self.make_private_if_parent_is_private()
		if not self.is_new():
			self.renumber_if_moved()
		self.set_idx()

	def renumber_if_moved(self):
		current_parent = frappe.db.get_value("Website Route", self.name, "parent_website_route")
		if current_parent and current_parent != self.parent_website_route:
			# move-up

			# sitemap
			frappe.db.sql("""update `tabWebsite Route` set idx=idx-1
				where parent_website_route=%s and idx>%s""", (current_parent, self.idx))

			# source table
			frappe.db.sql("""update `tab{0}` set idx=idx-1
				where parent_website_route=%s and idx>%s""".format(self.ref_doctype),
					(current_parent, self.idx))
			self.idx = None

	def on_update(self):
		if not frappe.flags.in_rebuild_config:
			NestedSet.on_update(self)
		self.clear_cache()

	def set_idx(self):
		if self.parent_website_route:
			if self.idx == None:
				self.set_idx_as_last()
			else:
				self.validate_previous_idx_exists()

	def set_idx_as_last(self):
		# new, append
		self.idx = int(frappe.db.sql("""select ifnull(max(ifnull(idx, -1)), -1)
			from `tabWebsite Route`
			where ifnull(parent_website_route, '')=%s and name!=%s""",
				(self.parent_website_route or '',
				self.name))[0][0]) + 1

	def validate_previous_idx_exists(self):
		self.idx = cint(self.idx)
		previous_idx = frappe.db.sql("""select max(idx)
			from `tab{}` where ifnull(parent_website_route, '')=%s
			and ifnull(idx, -1) < %s""".format(self.ref_doctype),
			(self.parent_website_route, self.idx))[0][0]

		if previous_idx and previous_idx != self.idx - 1:
			frappe.throw(_("Sitemap Ordering Error. Index {0} missing for {0}").format(self.idx-1, self.name))

	def rename(self):
		self.old_name = self.name
		self.name = self.get_url()
		frappe.db.sql("""update `tabWebsite Route` set name=%s where name=%s""",
			(self.name, self.old_name))
		self.rename_links()
		self.rename_descendants()
		self.clear_cache(self.old_name)

	def rename_links(self):
		for doctype in frappe.db.sql_list("""select parent from tabDocField where fieldtype='Link' and
			fieldname='parent_website_route' and options='Website Route'"""):
			for name in frappe.db.sql_list("""select name from `tab{}`
				where parent_website_route=%s""".format(doctype), self.old_name):
				frappe.db.set_value(doctype, name, "parent_website_route", self.name)

	def rename_descendants(self):
		# rename children
		for name in frappe.db.sql_list("""select name from `tabWebsite Route`
			where parent_website_route=%s""", self.name):
			child = frappe.get_doc("Website Route", name)
			child.parent_website_route = self.name
			child.save()

	def check_if_page_name_is_unique(self):
		exists = False
		if self.page_or_generator == "Page":
			# for a page, name and website sitemap config form a unique key
			exists = frappe.db.sql("""select name from `tabWebsite Route`
				where name=%s and website_template!=%s""", (self.name, self.website_template))
		else:
			# for a generator, name, ref_doctype and docname make a unique key
			exists = frappe.db.sql("""select name from `tabWebsite Route`
				where name=%s and (ifnull(ref_doctype, '')!=%s or ifnull(docname, '')!=%s)""",
				(self.name, self.ref_doctype, self.docname))

		if exists:
			frappe.throw(_("Page with name {0} already exists").format(self.name), frappe.NameError)

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
		clear_cache(name or self.name)
		if self.parent_website_route:
			clear_cache(self.parent_website_route)

def add_to_sitemap(options):
	website_route = frappe.new_doc("Website Route")

	for key in sitemap_fields:
		website_route.set(key, options.get(key))
	if not website_route.page_name:
		website_route.page_name = options.get("link_name")
	website_route.website_template = options.get("link_name")

	website_route.insert(ignore_permissions=True)

	return website_route.idx

def update_sitemap(website_route, options):
	website_route = frappe.get_doc("Website Route", website_route)

	for key in sitemap_fields:
		website_route.set(key, options.get(key))

	if not website_route.page_name:
		# for pages
		website_route.page_name = options.get("link_name")

	website_route.website_template = options.get("link_name")
	website_route.save(ignore_permissions=True)

	return website_route.idx

def remove_sitemap(page_name=None, ref_doctype=None, docname=None):
	if page_name:
		frappe.delete_doc("Website Route", page_name, ignore_permissions=True)
	elif ref_doctype and docname:
		frappe.delete_doc("Website Route", frappe.db.sql_list("""select name from `tabWebsite Route`
			where ref_doctype=%s and docname=%s""", (ref_doctype, docname)), ignore_permissions=True)

def cleanup_sitemap():
	"""remove sitemap records where its config do not exist anymore"""
	to_delete = frappe.db.sql_list("""select name from `tabWebsite Route` ws
			where not exists(select name from `tabWebsite Template` wsc
				where wsc.name=ws.website_template)""")

	frappe.delete_doc("Website Route", to_delete, ignore_permissions=True)
