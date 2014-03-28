# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
import os
from frappe import _
from frappe.website.doctype.website_route.website_route import add_to_sitemap, update_sitemap, cleanup_sitemap
from frappe.utils.nestedset import rebuild_tree

from frappe.model.document import Document

class WebsiteTemplate(Document):
		
	def after_insert(self):
		if self.page_or_generator == "Page":
			website_route = frappe.db.get_value("Website Route", 
				{"website_template": self.name, "page_or_generator": "Page"})
			
			opts = self.as_dict()
			opts.update({"public_read": 1})

			if website_route:
				update_sitemap(website_route, opts)
			else:
				add_to_sitemap(opts)
	
		else:
			condition = ""
			if self.condition_field:
				condition = " where ifnull(%s, 0)=1" % self.condition_field
						
			for name in frappe.db.sql_list("""select name from `tab{doctype}` 
				{condition} order by idx asc, {sort_field} {sort_order}""".format(
					doctype = self.ref_doctype,
					condition = condition,
					sort_field = getattr(self, "sort_field", "name"),
					sort_order = getattr(self, "sort_order", "asc")
				)):
				doc = frappe.get_doc(self.ref_doctype, name)
				
				# regenerate route
				doc.run_method("on_update")
		
def rebuild_website_template():
	# TODO
	frappe.flags.in_rebuild_config = True
		
	frappe.db.sql("""delete from `tabWebsite Template`""")
	for app in frappe.get_installed_apps():
		if app=="webnotes": app="frappe"
		build_website_template(app)
		
	cleanup_sitemap()
	
	frappe.flags.in_rebuild_config = False
	
	# enable nested set and rebuild
	rebuild_tree("Website Route", "parent_website_route")
	
	frappe.db.commit()


def build_website_template(app):		
	config = {"pages": {}, "generators":{}}
	
	pages, generators = get_pages_and_generators(app)
		
	for args in pages:
		add_website_template(**args)

	for args in generators:
		add_website_template(**args)
					
	frappe.db.commit()

def get_pages_and_generators(app):
	pages = []
	generators = []
	app_path = frappe.get_app_path(app)

	for config_type in ("pages", "generators"):
		path = os.path.join(app_path, "templates", config_type)
		if os.path.exists(path):
			for fname in os.listdir(path):
				fname = frappe.utils.cstr(fname)
				if fname.split(".")[-1] in ("html", "xml", "js", "css"):
					if config_type=="pages":
						pages.append({"page_or_generator": "Page", "app": app, "path": path,
							"fname":fname, "app_path":app_path})
					else:
						generators.append({"page_or_generator": "Generator", "app": app, "path": path,
							"fname":fname, "app_path":app_path})
						
	return pages, generators
	
def add_website_template(page_or_generator, app, path, fname, app_path):
	name = fname[:-5] if fname.endswith(".html") else fname
	
	wsc = frappe._dict({
		"doctype": "Website Template",
		"page_or_generator": page_or_generator,
		"link_name": name,
		"template_path": os.path.relpath(os.path.join(path, fname), app_path),
	})
	
	wsc.controller = get_template_controller(app, path, fname)
	
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
	
	if frappe.db.exists("Website Template", wsc.link_name):
		# found by earlier app, override
		frappe.db.sql("""delete from `tabWebsite Template` where name=%s""", (wsc.link_name,))
	
	frappe.get_doc(wsc).insert()
	
	return name
	
def get_template_controller(app, path, fname):
	controller = None
	controller_name = fname.split(".")[0].replace("-", "_") + ".py"
	controller_path = os.path.join(path, controller_name)
	if os.path.exists(controller_path):
		controller = app + "." + os.path.relpath(controller_path[:-3], frappe.get_app_path(app)).replace(os.path.sep, ".")
		
	return controller
	
