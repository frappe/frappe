# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.website.doctype.website_settings.website_settings import get_website_settings
from frappe.website.router import get_route_info

def get_context(path, args=None):
	context = get_route_info(path)

	if args:
		context.update(args)

	context = build_context(context)
	context["path"] = path

	return context

def build_context(context):
	"""get_context method of doc or module is supposed to render content templates and push it into context"""
	context = frappe._dict(context)
	if not "url_prefix" in context:
		context.url_prefix = ""
	context.update(get_website_settings())
	context.update(frappe.local.conf.get("website_context") or {})

	# provide doc
	if context.doc:
		context.update(context.doc.as_dict())
		context.update(context.doc.website)
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
			# get config fields
			for prop in ("base_template_path", "template", "no_cache", "no_sitemap",
				"condition_field"):
				if hasattr(module, prop):
					context[prop] = getattr(module, prop)

			if hasattr(module, "get_context"):
				ret = module.get_context(context)
				if ret:
					context.update(ret)

			if hasattr(module, "get_children"):
				context.children = module.get_children(context)

	add_metatags(context)

	# determine templates to be used
	if not context.base_template_path:
		app_base = frappe.get_hooks("base_template")
		context.base_template_path = app_base[0] if app_base else "templates/base.html"

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

