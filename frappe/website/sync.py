# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.modules import load_doctype_module
import statics, render

def sync(app=None):
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()

	print "Resetting..."
	render.clear_cache()

	# delete all static web pages
	statics.delete_static_web_pages()

	# delete all routes (resetting)
	frappe.db.sql("delete from `tabWebsite Route`")

	for app in apps:
		print "Importing pages from " + app
		sync_pages(app)
		print "Importing generators from " + app
		sync_generators(app)

	# sync statics
	print "Importing statics"
	statics_sync = statics.sync()
	statics_sync.start()

	# rebuild for new inserts
	statics_sync.start(rebuild=True)

def sync_pages(app):
	app_path = frappe.get_app_path(app)

	path = os.path.join(app_path, "templates", "pages")
	if os.path.exists(path):
		for fname in os.listdir(path):
			fname = frappe.utils.cstr(fname)
			page_name = fname.rsplit(".", 1)[0]
			if fname.split(".")[-1] in ("html", "xml", "js", "css"):
				# add website route
				route = frappe.new_doc("Website Route")
				route.page_or_generator = "Page"
				route.template = os.path.relpath(os.path.join(path, fname), app_path)
				route.page_name = page_name
				controller_path = os.path.join(path, page_name + ".py")

				if os.path.exists(controller_path):
					controller = app + "." + os.path.relpath(controller_path,
						app_path).replace(os.path.sep, ".")[:-3]
					route.controller = controller

				route.insert(ignore_permissions=True)

def sync_generators(app):
	for doctype in frappe.get_hooks("website_generators", app_name = app):
		condition, order_by = "", "name asc"
		module = load_doctype_module(doctype)
		if hasattr(module, "condition_field"):
			condition = " where ifnull({0}, 0)=1 ".format(module.condition_field)
		if hasattr(module, "sort_by"):
			order_by = "{0} {1}".format(module.sort_by, module.sort_order)
		for name in frappe.db.sql_list("select name from `tab{0}` {1} order by {2}".format(doctype,
			condition, order_by)):
			doc = frappe.get_doc(doctype, name)
			print doctype, name
			doc.save(ignore_permissions=True)
