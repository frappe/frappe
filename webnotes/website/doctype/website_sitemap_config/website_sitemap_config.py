# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.utils
import os

from webnotes.website.doctype.website_sitemap.website_sitemap import add_to_sitemap, update_sitemap, cleanup_sitemap
from webnotes.utils.nestedset import rebuild_tree

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def after_insert(self):
		if self.doc.page_or_generator == "Page":
			website_sitemap = webnotes.conn.get_value("Website Sitemap", 
				{"website_sitemap_config": self.doc.name, "page_or_generator": "Page"})
			
			if website_sitemap:
				update_sitemap(website_sitemap, self.doc.fields)
			else:
				add_to_sitemap(self.doc.fields)
	
		else:
			condition = ""
			if self.doc.condition_field:
				condition = " where ifnull(%s, 0)=1" % self.doc.condition_field
			
			for name in webnotes.conn.sql_list("""select name from `tab%s` %s""" \
				% (self.doc.ref_doctype, condition)):
				webnotes.bean(self.doc.ref_doctype, name).run_method("on_update")
		
def rebuild_website_sitemap_config():
	# TODO
	webnotes.flags.in_rebuild_config = True
	
	webnotes.conn.sql("""delete from `tabWebsite Sitemap Config`""")
	for app in webnotes.get_installed_apps():
		build_website_sitemap_config(app)
		
	cleanup_sitemap()
	
	webnotes.flags.in_rebuild_config = False
	
	# enable nested set and rebuild
	rebuild_tree("Website Sitemap", "parent_website_sitemap")
	
	webnotes.conn.commit()
		
def build_website_sitemap_config(app):		
	config = {"pages": {}, "generators":{}}
	basepath = webnotes.get_pymodule_path(app)
	
	# pages
	for config_type in ("pages", "generators"):
		path = os.path.join(basepath, "templates", config_type)
		if os.path.exists(path):
			for fname in os.listdir(path):
				fname = webnotes.utils.cstr(fname)
				if fname.split(".")[-1] in ("html", "xml", "js", "css"):
					name = add_website_sitemap_config("Page" if config_type=="pages" else "Generator", 
						app, path, fname, basepath)
					
	webnotes.conn.commit()

def add_website_sitemap_config(page_or_generator, app, path, fname, basepath):
	name = fname[:-5] if fname.endswith(".html") else fname
	
	wsc = webnotes._dict({
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
		module = webnotes.get_module(wsc.controller)
		wsc.no_cache = getattr(module, "no_cache", 0)
		wsc.no_sitemap = wsc.no_cache or getattr(module, "no_sitemap", 0)
		wsc.ref_doctype = getattr(module, "doctype", None)
		wsc.page_name_field = getattr(module, "page_name_field", "page_name")
		wsc.condition_field = getattr(module, "condition_field", None)
	
	if webnotes.conn.exists("Website Sitemap Config", wsc.link_name):
		# found by earlier app, override
		webnotes.conn.sql("""delete from `tabWebsite Sitemap Config` where name=%s""", (wsc.link_name,))
	
	webnotes.bean(wsc).insert()
	
	return name
