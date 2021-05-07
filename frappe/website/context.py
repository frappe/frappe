# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os, json

from frappe.website.doctype.website_settings.website_settings import get_website_settings
from frappe.website.router import get_page_context
from frappe.model.document import Document

def get_context(path, args=None):
	if args and args.source:
		context = args
	else:
		context = get_page_context(path)
		if args:
			context.update(args)

	if hasattr(frappe.local, 'request'):
		# for <body data-path=""> (remove leading slash)
		# path could be overriden in render.resolve_from_map
		context["path"] = frappe.local.request.path.strip('/ ')
	else:
		context["path"] = path

	context.canonical = frappe.utils.get_url(frappe.utils.escape_html(context.path))
	context.route = context.path
	context = build_context(context)

	# set using frappe.respond_as_web_page
	if hasattr(frappe.local, 'response') and frappe.local.response.get('context'):
		context.update(frappe.local.response.context)

	# to be able to inspect the context dict
	# Use the macro "inspect" from macros.html
	context._context_dict = context

	context.developer_mode = frappe.conf.developer_mode

	return context

def update_controller_context(context, controller):
	module = frappe.get_module(controller)

	if module:
		# get config fields
		for prop in ("base_template_path", "template", "no_cache", "sitemap",
			"condition_field"):
			if hasattr(module, prop):
				context[prop] = getattr(module, prop)

		if hasattr(module, "get_context"):
			import inspect
			try:
				if inspect.getfullargspec(module.get_context).args:
					ret = module.get_context(context)
				else:
					ret = module.get_context()
				if ret:
					context.update(ret)
			except (frappe.PermissionError, frappe.PageDoesNotExistError, frappe.Redirect):
				raise
			except:
				if not any([frappe.flags.in_migrate, frappe.flags.in_website_search_build]):
					frappe.errprint(frappe.utils.get_traceback())

		if hasattr(module, "get_children"):
			context.children = module.get_children(context)


def build_context(context):
	"""get_context method of doc or module is supposed to render
		content templates and push it into context"""
	context = frappe._dict(context)

	if not "url_prefix" in context:
		context.url_prefix = ""

	if context.url_prefix and context.url_prefix[-1]!='/':
		context.url_prefix += '/'

	# for backward compatibility
	context.docs_base_url = '/docs'

	context.update(get_website_settings(context))
	context.update(frappe.local.conf.get("website_context") or {})

	# provide doc
	if context.doc:
		context.update(context.doc.as_dict())
		context.update(context.doc.get_website_properties())

		if not context.template:
			context.template = context.doc.meta.get_web_template()

		if hasattr(context.doc, "get_context"):
			ret = context.doc.get_context(context)

			if ret:
				context.update(ret)

		for prop in ("no_cache", "sitemap"):
			if not prop in context:
				context[prop] = getattr(context.doc, prop, False)

	elif context.controller:
		# controller based context
		update_controller_context(context, context.controller)

		# controller context extensions
		context_controller_hooks = frappe.get_hooks("extend_website_page_controller_context") or {}
		for controller, extension in context_controller_hooks.items():
			if isinstance(extension, list):
				for ext in extension:
					if controller == context.controller:
						update_controller_context(context, ext)
			else:
				update_controller_context(context, extension)

	add_metatags(context)
	add_sidebar_and_breadcrumbs(context)

	# determine templates to be used
	if not context.base_template_path:
		app_base = frappe.get_hooks("base_template")
		context.base_template_path = app_base[-1] if app_base else "templates/base.html"

	if context.title_prefix and context.title and not context.title.startswith(context.title_prefix):
		context.title = '{0} - {1}'.format(context.title_prefix, context.title)

	# apply context from hooks
	update_website_context = frappe.get_hooks('update_website_context')
	for method in update_website_context:
		values = frappe.get_attr(method)(context)
		if values:
			context.update(values)

	return context

def load_sidebar(context, sidebar_json_path):
	with open(sidebar_json_path, 'r') as sidebarfile:
		try:
			sidebar_json = sidebarfile.read()
			context.sidebar_items = json.loads(sidebar_json)
			context.show_sidebar = 1
		except json.decoder.JSONDecodeError:
			frappe.throw('Invalid Sidebar JSON at ' + sidebar_json_path)

def get_sidebar_json_path(path, look_for=False):
	'''
		Get _sidebar.json path from directory path

		:param path: path of the current diretory
		:param look_for: if True, look for _sidebar.json going upwards from given path

		:return: _sidebar.json path
	'''
	if os.path.split(path)[1] == 'www' or path == '/' or not path:
		return ''

	sidebar_json_path = os.path.join(path, '_sidebar.json')
	if os.path.exists(sidebar_json_path):
		return sidebar_json_path
	else:
		if look_for:
			return get_sidebar_json_path(os.path.split(path)[0], look_for)
		else:
			return ''

def add_sidebar_and_breadcrumbs(context):
	'''Add sidebar and breadcrumbs to context'''
	from frappe.website.router import get_page_info_from_template
	if context.show_sidebar:
		context.no_cache = 1
		add_sidebar_data(context)
	else:
		if context.basepath:
			hooks = frappe.get_hooks('look_for_sidebar_json')
			look_for_sidebar_json = hooks[0] if hooks else 0
			sidebar_json_path = get_sidebar_json_path(
				context.basepath,
				look_for_sidebar_json
			)
			if sidebar_json_path:
				load_sidebar(context, sidebar_json_path)

	if context.add_breadcrumbs and not context.parents:
		if context.basepath:
			parent_path = os.path.dirname(context.path).rstrip('/')
			page_info = get_page_info_from_template(parent_path)
			if page_info:
				context.parents = [dict(route=parent_path, title=page_info.title)]

def add_sidebar_data(context):
	from frappe.utils.user import get_fullname_and_avatar
	import frappe.www.list

	if context.show_sidebar and context.website_sidebar:
		context.sidebar_items = frappe.get_all('Website Sidebar Item',
			filters=dict(parent=context.website_sidebar), fields=['title', 'route', '`group`'],
			order_by='idx asc')

	if not context.sidebar_items:
		sidebar_items = frappe.cache().hget('portal_menu_items', frappe.session.user)
		if sidebar_items == None:
			sidebar_items = []
			roles = frappe.get_roles()
			portal_settings = frappe.get_doc('Portal Settings', 'Portal Settings')

			def add_items(sidebar_items, items):
				for d in items:
					if d.get('enabled') and ((not d.get('role')) or d.get('role') in roles):
						sidebar_items.append(d.as_dict() if isinstance(d, Document) else d)

			if not portal_settings.hide_standard_menu:
				add_items(sidebar_items, portal_settings.get('menu'))

			if portal_settings.custom_menu:
				add_items(sidebar_items, portal_settings.get('custom_menu'))

			items_via_hooks = frappe.get_hooks('portal_menu_items')
			if items_via_hooks:
				for i in items_via_hooks: i['enabled'] = 1
				add_items(sidebar_items, items_via_hooks)

			frappe.cache().hset('portal_menu_items', frappe.session.user, sidebar_items)

		context.sidebar_items = sidebar_items

	info = get_fullname_and_avatar(frappe.session.user)
	context["fullname"] = info.fullname
	context["user_image"] = info.avatar
	context["user"] = info.name


def add_metatags(context):
	tags = frappe._dict(context.get("metatags") or {})

	if "og:type" not in tags:
		tags["og:type"] = "article"

	if "title" not in tags and context.title:
		tags["title"] = context.title

	title = tags.get("name") or tags.get("title")
	if title:
		tags["og:title"] = tags["twitter:title"] = title
		tags["twitter:card"] = "summary"

	if "description" not in tags and context.description:
		tags["description"] = context.description

	description = tags.get("description")
	if description:
		tags["og:description"] = tags["twitter:description"] = description

	if "image" not in tags and context.image:
		tags["image"] = context.image

	image = tags.get("image")
	if image:
		tags["og:image"] = tags["twitter:image"] = tags["image"] = frappe.utils.get_url(image)
		tags['twitter:card'] = "summary_large_image"

	if "author" not in tags and context.author:
		tags["author"] = context.author

	tags["og:url"] = tags["url"] = frappe.utils.get_url(context.path)

	if "published_on" not in tags and context.published_on:
		tags["published_on"] = context.published_on

	if "published_on" in tags:
		tags["datePublished"] = tags["published_on"]
		del tags["published_on"]

	tags["language"] = frappe.local.lang or "en"

	# Get meta tags from Website Route meta
	# they can override the defaults set above
	route = context.path
	if route == '':
		# homepage
		route = frappe.db.get_single_value('Website Settings', 'home_page')

	route_exists = (route
		and not route.endswith(('.js', '.css'))
		and frappe.db.exists('Website Route Meta', route))

	if route_exists:
		website_route_meta = frappe.get_doc('Website Route Meta', route)
		for meta_tag in website_route_meta.meta_tags:
			d = meta_tag.get_meta_dict()
			tags.update(d)

	# update tags in context
	context.metatags = tags
