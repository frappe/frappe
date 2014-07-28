# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os, sys
from frappe.modules import load_doctype_module
from frappe.utils.nestedset import rebuild_tree
from frappe.utils import update_progress_bar
import statics, render

all_routes = None

def sync(app=None, verbose=False):
	global all_routes
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()

	render.clear_cache()

	all_routes = frappe.db.sql_list("select name from `tabWebsite Route`")

	# pages
	pages = []
	for app in apps:
		pages += get_sync_pages(app)
	sync_pages(pages)

	# sync statics (make generators)
	statics_sync = statics.sync(verbose=verbose)
	statics_sync.start()

	# generators
	generators = []
	for app in apps:
		generators += get_sync_generators(app)
	sync_generators(generators)

	# delete remaining routes
	for r in all_routes:
		frappe.delete_doc("Website Route", r, force=True)

def sync_pages(routes):
	global all_routes
	l = len(routes)
	if l:
		for i, r in enumerate(routes):
			r.autoname()
			if frappe.db.exists("Website Route", r.name):
				route = frappe.get_doc("Website Route", r.name)
				for key in ("page_title", "controller", "template"):
					route.set(key, r.get(key))
				route.save(ignore_permissions=True)
			else:
				r.insert(ignore_permissions=True)

			if r.name in all_routes:
				all_routes.remove(r.name)
			update_progress_bar("Updating Pages", i, l)

		print ""

def sync_generators(generators):
	global all_routes
	l = len(generators)
	if l:
		frappe.flags.in_sync_website = True
		for i, g in enumerate(generators):
			doc = frappe.get_doc(g[0], g[1])
			doc.update_sitemap()
			route = doc.get_route()
			if route in all_routes:
				all_routes.remove(route)
			update_progress_bar("Updating Generators", i, l)
			sys.stdout.flush()

		frappe.flags.in_sync_website = False
		rebuild_tree("Website Route", "parent_website_route")

		# HACK! update public_read, public_write
		for name in frappe.db.sql_list("""select name from `tabWebsite Route` where ifnull(parent_website_route, '')!=''
			order by lft"""):
			route = frappe.get_doc("Website Route", name)
			route.make_private_if_parent_is_private()
			route.db_update()

		print ""

def get_sync_pages(app):
	app_path = frappe.get_app_path(app)
	pages = []

	path = os.path.join(app_path, "templates", "pages")
	if os.path.exists(path):
		for fname in os.listdir(path):
			fname = frappe.utils.cstr(fname)
			page_name, extn = fname.rsplit(".", 1)
			if extn in ("html", "xml", "js", "css"):
				route_page_name = page_name if extn=="html" else fname

				# add website route
				route = frappe.new_doc("Website Route")
				route.page_or_generator = "Page"
				route.template = os.path.relpath(os.path.join(path, fname), app_path)
				route.page_name = route_page_name
				route.public_read = 1
				controller_path = os.path.join(path, page_name + ".py")

				if os.path.exists(controller_path):
					controller = app + "." + os.path.relpath(controller_path,
						app_path).replace(os.path.sep, ".")[:-3]
					route.controller = controller
					try:
						route.page_title = frappe.get_attr(controller + "." + "page_title")
					except AttributeError:
						pass

				pages.append(route)

	return pages

def get_sync_generators(app):
	generators = []
	for doctype in frappe.get_hooks("website_generators", app_name = app):
		condition, order_by = "", "name asc"
		module = load_doctype_module(doctype)
		if hasattr(module, "condition_field"):
			condition = " where ifnull({0}, 0)=1 ".format(module.condition_field)
		if hasattr(module, "order_by"):
			order_by = module.order_by
		for name in frappe.db.sql_list("select name from `tab{0}` {1} order by {2}".format(doctype,
			condition, order_by)):
			generators.append((doctype, name))

	return generators
