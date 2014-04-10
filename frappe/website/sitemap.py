# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.website.utils import scrub_relative_urls, get_home_page, can_cache

def get_sitemap_options(path):
	sitemap_options = None
	cache_key = "sitemap_options:{}".format(path)

	if can_cache():
		sitemap_options = frappe.cache().get_value(cache_key)

	if not sitemap_options:
		sitemap_options = build_sitemap_options(path)
		if can_cache(sitemap_options.no_cache):
			frappe.cache().set_value(cache_key, sitemap_options)

	return frappe._dict(sitemap_options)

def build_sitemap_options(path):
	sitemap_options = frappe._dict(frappe.get_doc("Website Route", path).as_dict())
	home_page = get_home_page()

	sitemap_config = frappe.get_doc("Website Template",
		sitemap_options.get("website_template")).as_dict()

	# get sitemap config fields too
	for fieldname in ("base_template_path", "template_path", "controller",
		"no_cache", "no_sitemap", "page_name_field", "condition_field"):
		sitemap_options[fieldname] = sitemap_config.get(fieldname)

	sitemap_options.doctype = sitemap_options.ref_doctype
	sitemap_options.title = sitemap_options.page_title
	sitemap_options.pathname = sitemap_options.name

	# establish hierarchy
	sitemap_options.parents = frappe.db.sql("""select name, page_title from `tabWebsite Route`
		where lft < %s and rgt > %s order by lft asc""", (sitemap_options.lft, sitemap_options.rgt), as_dict=True)

	if not sitemap_options.no_sidebar:
		sitemap_options.children = get_route_children(sitemap_options.pathname, home_page)

		if not sitemap_options.children and sitemap_options.parent_website_route \
			and sitemap_options.parent_website_route!=home_page:
			sitemap_options.children = get_route_children(sitemap_options.parent_website_route, home_page)

	# determine templates to be used
	if not sitemap_options.base_template_path:
		app_base = frappe.get_hooks("base_template")
		sitemap_options.base_template_path = app_base[0] if app_base else "templates/base.html"

	return sitemap_options

def get_route_children(pathname, home_page=None):
	if not home_page:
		home_page = get_home_page()

	if pathname==home_page or not pathname:
		children = frappe.db.sql("""select url as name, label as page_title,
			1 as public_read from `tabTop Bar Item` where parentfield='sidebar_items' order by idx""",
			as_dict=True)
	else:
		children = frappe.db.sql("""select * from `tabWebsite Route`
			where ifnull(parent_website_route,'')=%s
			and public_read=1
			order by idx, page_title asc""", pathname, as_dict=True)

		if children:
			# if children are from generator and sort order is specified, then get that condition
			website_template = frappe.get_doc("Website Template", children[0].website_template)
			if website_template.sort_by!="name":
				children = frappe.db.sql("""select t1.* from
					`tabWebsite Route` t1, `tab{ref_doctype}` t2
					where ifnull(t1.parent_website_route,'')=%s
					and t1.public_read=1
					and t1.docname = t2.name
					order by t2.{sort_by} {sort_order}""".format(**website_template.as_dict()),
						pathname, as_dict=True)

			children = [frappe.get_doc("Website Route", pathname)] + children

	return children
