# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.website.doctype.website_settings.website_settings import get_website_settings
from frappe.website.template import render_blocks
from frappe.website.router import get_route_info
from frappe.website.utils import can_cache

def get_context(path):
	context = None
	cache_key = "page_context:{}".format(path)

	def add_data_path(context):
		if not context.data:
			context.data = {}

		context.data["path"] = path

	# try from memcache
	if can_cache():
		context = frappe.cache().get_value(cache_key)

	if not context:
		context = get_route_info(path)

		# permission may be required for rendering
		context["access"] = frappe._dict({"public_read":1, "public_write":1})

		context = build_context(context)
		add_data_path(context)

		if can_cache(context.no_cache):
			frappe.cache().set_value(cache_key, context)

	else:
		context["access"] = frappe._dict({"public_read":1, "public_write":1})
		add_data_path(context)

	context.update(context.data or {})

	return context

def build_context(sitemap_options):
	"""get_context method of doc or module is supposed to render content templates and push it into context"""
	context = frappe._dict(sitemap_options)
	context.update(get_website_settings())

	# provide doc
	if context.doc:
		context.update(context.doc.as_dict())
		if hasattr(context.doc, "get_context"):
			ret = context.doc.get_context(context)
			if ret:
				context.update(ret)

		for prop in ("no_cache", "no_sitemap"):
			if not prop in context:
				context[prop] = getattr(context.doc, prop, False)

	elif context.controller:
		module = frappe.get_module(context.controller)

		if module:
			if hasattr(module, "get_context"):
				ret = module.get_context(context)
				if ret:
					context.update(ret)
			if hasattr(module, "get_children"):
				context.children = module.get_children(context)

	add_metatags(context)

	if context.get("base_template_path") != context.get("template") and not context.get("rendered"):
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


