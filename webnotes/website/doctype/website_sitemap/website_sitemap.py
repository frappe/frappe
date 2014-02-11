# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _
from webnotes.utils.nestedset import DocTypeNestedSet

sitemap_fields = ("page_name", "ref_doctype", "docname", "page_or_generator", 
	"lastmod", "parent_website_sitemap", "public_read", "public_write", "page_title")

class DocType(DocTypeNestedSet):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		self.nsm_parent_field = "parent_website_sitemap"
		
	def autoname(self):
		self.doc.name = self.get_url()

	def get_url(self):
		url = self.doc.page_name
		if self.doc.parent_website_sitemap:
			url = self.doc.parent_website_sitemap + "/" + url
			
		return url
		
	def validate(self):
		if self.get_url() != self.doc.name:
			self.rename()
		self.check_if_page_name_is_unique()
		self.make_private_if_parent_is_private()
	
	def rename(self):
		from webnotes.webutils import clear_cache
		self.old_name = self.doc.name
		self.doc.name = self.get_url()
		webnotes.conn.sql("""update `tabWebsite Sitemap` set name=%s where name=%s""", 
			(self.doc.name, self.old_name))
		self.rename_links()
		self.rename_descendants()
		clear_cache(self.old_name)

	def rename_links(self):
		for doctype in webnotes.conn.sql_list("""select parent from tabDocField where fieldtype='Link' and 
			fieldname='parent_website_sitemap' and options='Website Sitemap'"""):
			for name in webnotes.conn.sql_list("""select name from `tab{}` 
				where parent_website_sitemap=%s""".format(doctype), self.old_name):
				webnotes.conn.set_value(doctype, name, "parent_website_sitemap", self.doc.name)
				
	def rename_descendants(self):
		# rename children
		for name in webnotes.conn.sql_list("""select name from `tabWebsite Sitemap`
			where parent_website_sitemap=%s""", self.doc.name):
			child = webnotes.bean("Website Sitemap", name)
			child.doc.parent_website_sitemap = self.doc.name
			child.save()
	
	def on_update(self):
		if not webnotes.flags.in_rebuild_config:
			DocTypeNestedSet.on_update(self)
		
	def check_if_page_name_is_unique(self):
		exists = False
		if self.doc.page_or_generator == "Page":
			# for a page, name and website sitemap config form a unique key
			exists = webnotes.conn.sql("""select name from `tabWebsite Sitemap`
				where name=%s and website_sitemap_config!=%s""", (self.doc.name, self.doc.website_sitemap_config))
		else:
			# for a generator, name, ref_doctype and docname make a unique key
			exists = webnotes.conn.sql("""select name from `tabWebsite Sitemap`
				where name=%s and (ifnull(ref_doctype, '')!=%s or ifnull(docname, '')!=%s)""", 
				(self.doc.name, self.doc.ref_doctype, self.doc.docname))
				
		if exists:
			webnotes.throw("{}: {}. {}.".format(_("A Website Page already exists with the Page Name"), 
				self.doc.name, _("Please change it to continue")))
		
	def make_private_if_parent_is_private(self):
		if self.doc.parent_website_sitemap:
			parent_pubic_read = webnotes.conn.get_value("Website Sitemap", self.doc.parent_website_sitemap,
				"public_read")
			
			if not parent_pubic_read:
				self.doc.public_read = self.doc.public_write = 0
			
	def on_trash(self):		
		from webnotes.webutils import clear_cache
		# remove website sitemap permissions
		to_remove = webnotes.conn.sql_list("""select name from `tabWebsite Sitemap Permission` 
			where website_sitemap=%s""", (self.doc.name,))
		webnotes.delete_doc("Website Sitemap Permission", to_remove, ignore_permissions=True)
		
		clear_cache(self.doc.name)
		
def add_to_sitemap(options):
	bean = webnotes.new_bean("Website Sitemap")

	for key in sitemap_fields:
		bean.doc.fields[key] = options.get(key)
	if not bean.doc.page_name:
		bean.doc.page_name = options.link_name
	bean.doc.website_sitemap_config = options.link_name

	bean.insert(ignore_permissions=True)
	
def update_sitemap(website_sitemap, options):
	bean = webnotes.bean("Website Sitemap", website_sitemap)
	
	for key in sitemap_fields:
		bean.doc.fields[key] = options.get(key)
	if not bean.doc.page_name:
		# for pages
		bean.doc.page_name = options.link_name
	
	bean.doc.website_sitemap_config = options.link_name
		
	bean.save(ignore_permissions=True)
	
def remove_sitemap(page_name=None, ref_doctype=None, docname=None):
	if page_name:
		webnotes.delete_doc("Website Sitemap", page_name, ignore_permissions=True)
	elif ref_doctype and docname:
		webnotes.delete_doc("Website Sitemap", webnotes.conn.sql_list("""select name from `tabWebsite Sitemap`
			where ref_doctype=%s and docname=%s""", (ref_doctype, docname)), ignore_permissions=True)
	
def cleanup_sitemap():
	"""remove sitemap records where its config do not exist anymore"""
	to_delete = webnotes.conn.sql_list("""select name from `tabWebsite Sitemap` ws
			where not exists(select name from `tabWebsite Sitemap Config` wsc
				where wsc.name=ws.website_sitemap_config)""")
	
	webnotes.delete_doc("Website Sitemap", to_delete, ignore_permissions=True)