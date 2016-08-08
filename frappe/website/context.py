# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json

from frappe.website.doctype.website_settings.website_settings import get_website_settings
from frappe.website.router import get_page_context

def get_context(path, args=None):
	if args and args.source:
		context = args
	else:
		context = get_page_context(path)
		if args:
			context.update(args)

	context = build_context(context)

	if hasattr(frappe.local, 'request'):
		# for <body data-path=""> (remove leading slash)
		# path could be overriden in render.resolve_from_map
		context["path"] = frappe.local.request.path[1:]
	else:
		context["path"] = path

	# set using frappe.respond_as_web_page
	if hasattr(frappe.local, 'response') and frappe.local.response.get('context'):
		context.update(frappe.local.response.context)

	# print frappe.as_json(context)

	return context

def build_context(context):
	"""get_context method of doc or module is supposed to render
		content templates and push it into context"""
	context = frappe._dict(context)

	if not "url_prefix" in context:
		context.url_prefix = ""

	if context.url_prefix and context.url_prefix[-1]!='/':
		context.url_prefix += '/'

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

	if context.show_sidebar:
		add_sidebar_data(context)

	# determine templates to be used
	if not context.base_template_path:
		app_base = frappe.get_hooks("base_template")
		context.base_template_path = app_base[0] if app_base else "templates/base.html"

	return context

def add_sidebar_data(context):
	from frappe.utils.user import get_fullname_and_avatar
	import frappe.www.list

	sidebar_items = json.loads(frappe.cache().get('sidebar_items') or '[]')
	if not sidebar_items:
		sidebar_items = frappe.get_all('Portal Menu Item',
			fields=['title', 'route', 'reference_doctype', 'show_always'],
			filters={'enabled': 1}, order_by='idx asc')
		frappe.cache().set('portal_menu_items', json.dumps(sidebar_items))

	if not context.sidebar_items:
		context.sidebar_items = sidebar_items

	info = get_fullname_and_avatar(frappe.session.user)
	context["fullname"] = info.fullname
	context["user_image"] = info.avatar


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

