# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
import os
from frappe import _
from frappe.website.doctype.website_sitemap.website_sitemap import add_to_sitemap, update_sitemap, cleanup_sitemap
from frappe.utils.nestedset import rebuild_tree

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def after_insert(self):
		if self.doc.page_or_generator == "Page":
			website_sitemap = frappe.conn.get_value("Website Sitemap", 
				{"website_sitemap_config": self.doc.name, "page_or_generator": "Page"})
			
			opts = self.doc.fields.copy()
			opts.update({"public_read": 1})
			
			if website_sitemap:
				update_sitemap(website_sitemap, opts)
			else:
				add_to_sitemap(opts)
	
		else:
			condition = ""
			if self.doc.condition_field:
				condition = " where ifnull(%s, 0)=1" % self.doc.condition_field
			
			for name in frappe.conn.sql_list("""select name from `tab{doctype}` 
				{condition} order by {sort_field} {sort_order}""".format(
					doctype = self.doc.ref_doctype,
					condition = condition,
					sort_field = self.doc.sort_field or "name",
					sort_order = self.doc.sort_order or "asc"
				)):
				frappe.bean(self.doc.ref_doctype, name).run_method("on_update")
		
def rebuild_website_sitemap_config():
	# TODO
	frappe.flags.in_rebuild_config = True
	
	frappe.conn.sql("""update `tabWeb Page` set idx=null""")
	frappe.conn.sql("""update `tabBlog Post` set idx=null""")
	frappe.conn.sql("""update `tabBlog Category` set idx=null""")
	frappe.conn.sql("""update `tabWebsite Group` set idx=null""")
	
	frappe.conn.sql("""delete from `tabWebsite Sitemap Config`""")
	for app in frappe.get_installed_apps():
		if app=="webnotes": app="frappe"
		build_website_sitemap_config(app)
		
	cleanup_sitemap()
	
	frappe.flags.in_rebuild_config = False
	
	# enable nested set and rebuild
	rebuild_tree("Website Sitemap", "parent_website_sitemap")
	
	frappe.conn.commit()
		
def build_website_sitemap_config(app):		
	config = {"pages": {}, "generators":{}}
	basepath = frappe.get_pymodule_path(app)
	
	pages = []
	generators = []

	for config_type in ("pages", "generators"):
		path = os.path.join(basepath, "templates", config_type)
		if os.path.exists(path):
			for fname in os.listdir(path):
				fname = frappe.utils.cstr(fname)
				if fname.split(".")[-1] in ("html", "xml", "js", "css"):
					if config_type=="pages":
						pages.append(["Page", app, path, fname, basepath])
					else:
						generators(["Generator", app, path, fname, basepath])

	for args in pages:
		add_website_sitemap_config(*args)

	for args in generators:
		add_website_sitemap_config(*args)
					
	frappe.conn.commit()

def add_website_sitemap_config(page_or_generator, app, path, fname, basepath):
	name = fname[:-5] if fname.endswith(".html") else fname
	
	wsc = frappe._dict({
		"doctype": "Website Sitemap Config",
		"page_or_generator": page_or_generator,
		"link_name": name,
		"template_path": os.path.relpath(os.path.join(path, fname), basepath),
	})
		
	controller_name = fname.split(".")[0].replace("-", "_") + ".py"
	controller_path = os.path.join(path, controller_name)
	if os.path.exists(controller_path):
		wsc.controller = app + "." + os.path.relpath(controller_path[:-3], basepath).replace(os.path.sep, ".")

	if wsc.controller:
		# verbose print wsc.controller
		module = frappe.get_module(wsc.controller)
		wsc.no_cache = getattr(module, "no_cache", 0)
		wsc.no_sitemap = wsc.no_cache or getattr(module, "no_sitemap", 0)
		wsc.no_sidebar = wsc.no_sidebar or getattr(module, "no_sidebar", 0)
		wsc.ref_doctype = getattr(module, "doctype", None)
		wsc.page_name_field = getattr(module, "page_name_field", "page_name")
		wsc.condition_field = getattr(module, "condition_field", None)
		wsc.sort_by = getattr(module, "sort_by", "name")
		wsc.sort_order = getattr(module, "sort_order", "asc")
		wsc.base_template_path = getattr(module, "base_template_path", None)
		wsc.page_title = getattr(module, "page_title", _(name.title()))
	
	if frappe.conn.exists("Website Sitemap Config", wsc.link_name):
		# found by earlier app, override
		frappe.conn.sql("""delete from `tabWebsite Sitemap Config` where name=%s""", (wsc.link_name,))
	
	frappe.bean(wsc).insert()
	
	return name
