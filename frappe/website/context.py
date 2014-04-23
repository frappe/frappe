# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

# frequently used imports (used by other modules)
from frappe.website.permissions import get_access

from frappe.website.doctype.website_settings.website_settings import get_website_settings
from frappe.website.template import render_blocks
from frappe.website.sitemap import get_sitemap_options
from frappe.website.utils import can_cache

def get_context(path):
	context = None
	cache_key = "page_context:{}".format(path)

	# try from memcache
	if can_cache():
		context = frappe.cache().get_value(cache_key)

	if not context:
		context = get_sitemap_options(path)

		# permission may be required for rendering
		context["access"] = get_access(context.pathname)

		context = build_context(context)

		if can_cache(context.no_cache):
			frappe.cache().set_value(cache_key, context)

	else:
		context["access"] = get_access(context.pathname)

	if not context.data:
		context.data = {}
	context.data["path"] = path
	context.update(context.data or {})

	return context

def build_context(sitemap_options):
	"""get_context method of doc or module is supposed to render content templates and push it into context"""
	context = frappe._dict(sitemap_options)
	context.update(get_website_settings())

	# provide doc
	if context.doctype and context.docname:
		context.doc = frappe.get_doc(context.doctype, context.docname)

	if context.controller:
		module = frappe.get_module(context.controller)

		if module and hasattr(module, "get_context"):
			context.update(module.get_context(context) or {})

	add_metatags(context)

	if context.get("base_template_path") != context.get("template_path") and not context.get("rendered"):
		context.data = render_blocks(context)

	return context

def add_metatags(context):
	tags = context.get("metatags")
	if tags:
		if not "twitter:card" in tags:
			tags["twitter:card"] = "summary"
		if not "og:type" in tags:
			tags["og:type"] = "article"
		if tags.get("name"):
			tags["og:title"] = tags["twitter:title"] = tags["name"]
		if tags.get("description"):
			tags["og:description"] = tags["twitter:description"] = tags["description"]
		if tags.get("image"):
			tags["og:image"] = tags["twitter:image:src"] = tags["image"]


