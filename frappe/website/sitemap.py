# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os

from frappe.website.utils import can_cache, delete_page_cache
from frappe.model.document import get_controller

def get_sitemap_options(path):
	sitemap_options = None
	cache_key = "sitemap_options:{}".format(path)

	if can_cache():
		sitemap_options = frappe.cache().get_value(cache_key)

	if not sitemap_options:
		sitemap_options = build_sitemap_options(path)
		if can_cache(sitemap_options.no_cache):
			frappe.cache().set_value(cache_key, sitemap_options)

	return sitemap_options

def build_sitemap_options(path):
	sitemap_options = resolve_route(path)
	if not sitemap_options:
		raise frappe.DoesNotExistError

	if sitemap_options.controller:
		module = frappe.get_module(sitemap_options.controller)

		# get sitemap config fields too
		for prop in ("base_template_path", "template", "no_cache", "no_sitemap",
			"condition_field"):
			if hasattr(module, prop):
				sitemap_options[prop] = getattr(module, prop)

	sitemap_options.doctype = sitemap_options.ref_doctype
	sitemap_options.title = sitemap_options.page_title
	sitemap_options.pathname = path

	# determine templates to be used
	if not sitemap_options.base_template_path:
		app_base = frappe.get_hooks("base_template")
		sitemap_options.base_template_path = app_base[0] if app_base else "templates/base.html"

	return sitemap_options

def resolve_route(path):
	route = get_page_route(path)
	if route:
		return route

	return get_generator_route(path)

def get_page_route(path):
	found = filter(lambda p: p.page_name==path, get_pages())
	return found[0] if found else None

def get_generator_route(path):
	def get_route(doctype, condition_field, order_by):
		condition = []
		if condition_field:
			condition.append("ifnull({0}, 0)=1".format(condition_field))
		meta = frappe.get_meta(doctype)

		if meta.get_field("parent_website_route"):
			condition.append("""concat(ifnull(parent_website_route, ""),
				if(ifnull(parent_website_route, "")="", "", "/"), page_name) = %s""")
		else:
			condition.append("page_name = %s")

		g = frappe.db.sql("""select name from `tab{0}` where {1}
			 order by {2}""".format(doctype, " and ".join(condition), order_by), path)

		if g:
			return frappe.get_doc(doctype, g[0][0]).get_website_route()

	return process_generators(get_route)

def clear_sitemap():
	for p in get_pages():
		delete_page_cache(p.name)

	def clear_generators(doctype, condition_field, order_by):
		meta = frappe.get_meta(doctype)
		query = "select page_name from `tab{0}`"
		if meta.get_field("parent_website_route"):
			query = """select concat(ifnull(parent_website_route, ""),
				if(ifnull(parent_website_route, "")="", "", "/"), page_name) from `tab{0}`"""
		for route in frappe.db.sql_list(query.format(doctype)):
			if route:
				delete_page_cache(route)

	process_generators(clear_generators)

def process_generators(func):
	for app in frappe.get_installed_apps():
		for doctype in frappe.get_hooks("website_generators", app_name = app):
			order_by = "name asc"
			condition_field = None
			controller = get_controller(doctype)

			if hasattr(controller, "condition_field"):
				condition_field = controller.condition_field
			if hasattr(controller, "order_by"):
				order_by = controller.order_by

			val = func(doctype, condition_field, order_by)
			if val:
				return val

def get_pages():
	pages = frappe.cache().get_value("_website_pages")
	if not pages:
		pages = []
		for app in frappe.get_installed_apps():
			app_path = frappe.get_app_path(app)
			path = os.path.join(app_path, "templates", "pages")
			if os.path.exists(path):
				for fname in os.listdir(path):
					fname = frappe.utils.cstr(fname)
					page_name, extn = fname.rsplit(".", 1)
					if extn in ("html", "xml", "js", "css"):
						route_page_name = page_name if extn=="html" else fname

						# add website route
						route = frappe._dict()
						route.page_or_generator = "Page"
						route.template = os.path.relpath(os.path.join(path, fname), app_path)
						route.name = route.page_name = route_page_name
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

		frappe.cache().set_value("_website_pages", pages)
	return pages
