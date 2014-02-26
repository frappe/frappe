# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.nestedset import DocTypeNestedSet

sitemap_fields = ("page_name", "ref_doctype", "docname", "page_or_generator", "idx",
	"lastmod", "parent_website_route", "public_read", "public_write", "page_title")

class DocType(DocTypeNestedSet):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		self.nsm_parent_field = "parent_website_route"
		
	def autoname(self):
		self.doc.name = self.get_url()

	def get_url(self):
		url = self.doc.page_name
		if self.doc.parent_website_route:
			url = self.doc.parent_website_route + "/" + url
		return url
		
	def validate(self):
		if self.get_url() != self.doc.name:
			self.rename()
		self.check_if_page_name_is_unique()
		self.make_private_if_parent_is_private()
		if not self.doc.is_new():
			self.renumber_if_moved()
		self.set_idx()

	def renumber_if_moved(self):
		current_parent = frappe.db.get_value("Website Route", self.doc.name, "parent_website_route")
		if current_parent and current_parent != self.doc.parent_website_route:
			# move-up
			
			# sitemap
			frappe.db.sql("""update `tabWebsite Route` set idx=idx-1 
				where parent_website_route=%s and idx>%s""", (current_parent, self.doc.idx))
				
			# source table
			frappe.db.sql("""update `tab{0}` set idx=idx-1 
				where parent_website_route=%s and idx>%s""".format(self.doc.ref_doctype), 
					(current_parent, self.doc.idx))
			self.doc.idx = None
	
	def set_idx(self):
		if self.doc.parent_website_route:
			if self.doc.idx == None:
				self.doc.idx = int(frappe.db.sql("""select ifnull(max(ifnull(idx, -1)), -1) 
					from `tabWebsite Route`
					where ifnull(parent_website_route, '')=%s and name!=%s""", 
						(self.doc.parent_website_route or '',
						self.doc.name))[0][0]) + 1
								
			else:
				self.doc.idx = cint(self.doc.idx)
				previous_idx = frappe.db.sql("""select max(idx) 
						from `tab{}` where ifnull(parent_website_route, '')=%s 
						and ifnull(idx, -1) < %s""".format(self.doc.ref_doctype), 
						(self.doc.parent_website_route, self.doc.idx))[0][0]
				
				if previous_idx and previous_idx != self.doc.idx - 1:
					frappe.throw("{}: {}, {}".format(
						_("Sitemap Ordering Error. Index missing"), self.doc.name, self.doc.idx-1))

	def on_update(self):
		if not frappe.flags.in_rebuild_config:
			DocTypeNestedSet.on_update(self)
												
	def rename(self):
		from frappe.website.render import clear_cache
		self.old_name = self.doc.name
		self.doc.name = self.get_url()
		frappe.db.sql("""update `tabWebsite Route` set name=%s where name=%s""", 
			(self.doc.name, self.old_name))
		self.rename_links()
		self.rename_descendants()
		clear_cache(self.old_name)
		
	def rename_links(self):
		for doctype in frappe.db.sql_list("""select parent from tabDocField where fieldtype='Link' and 
			fieldname='parent_website_route' and options='Website Route'"""):
			for name in frappe.db.sql_list("""select name from `tab{}` 
				where parent_website_route=%s""".format(doctype), self.old_name):
				frappe.db.set_value(doctype, name, "parent_website_route", self.doc.name)
	
	def rename_descendants(self):
		# rename children
		for name in frappe.db.sql_list("""select name from `tabWebsite Route`
			where parent_website_route=%s""", self.doc.name):
			child = frappe.bean("Website Route", name)
			child.doc.parent_website_route = self.doc.name
			child.save()
		
	def check_if_page_name_is_unique(self):
		exists = False
		if self.doc.page_or_generator == "Page":
			# for a page, name and website sitemap config form a unique key
			exists = frappe.db.sql("""select name from `tabWebsite Route`
				where name=%s and website_template!=%s""", (self.doc.name, self.doc.website_template))
		else:
			# for a generator, name, ref_doctype and docname make a unique key
			exists = frappe.db.sql("""select name from `tabWebsite Route`
				where name=%s and (ifnull(ref_doctype, '')!=%s or ifnull(docname, '')!=%s)""", 
				(self.doc.name, self.doc.ref_doctype, self.doc.docname))
				
		if exists:
			frappe.throw("{}: {}. {}.".format(_("A Website Page already exists with the Page Name"), 
				self.doc.name, _("Please change it to continue")))
		
	def make_private_if_parent_is_private(self):
		if self.doc.parent_website_route:
			parent_pubic_read = frappe.db.get_value("Website Route", self.doc.parent_website_route,
				"public_read")
			
			if not parent_pubic_read:
				self.doc.public_read = self.doc.public_write = 0
			
	def on_trash(self):		
		from frappe.website.render import clear_cache
		# remove website sitemap permissions
		to_remove = frappe.db.sql_list("""select name from `tabWebsite Route Permission` 
			where website_route=%s""", (self.doc.name,))
		frappe.delete_doc("Website Route Permission", to_remove, ignore_permissions=True)
		
		clear_cache(self.doc.name)
		
def add_to_sitemap(options):
	bean = frappe.new_bean("Website Route")

	for key in sitemap_fields:
		bean.doc.fields[key] = options.get(key)
	if not bean.doc.page_name:
		bean.doc.page_name = options.link_name
	bean.doc.website_template = options.link_name

	bean.insert(ignore_permissions=True)
	
	return bean.doc.idx
	
def update_sitemap(website_route, options):
	bean = frappe.bean("Website Route", website_route)
	
	for key in sitemap_fields:
		bean.doc.fields[key] = options.get(key)
	
	if not bean.doc.page_name:
		# for pages
		bean.doc.page_name = options.link_name
		
	bean.doc.website_template = options.link_name	
	bean.save(ignore_permissions=True)

	return bean.doc.idx
	
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
