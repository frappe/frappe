# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os

from frappe.website.utils import can_cache, delete_page_cache
from frappe.model.document import get_controller
from frappe import _

def get_page_context(path):
	page_context = None
	if can_cache():
		page_context_cache = frappe.cache().hget("page_context", path) or {}
		page_context = page_context_cache.get(frappe.local.lang, None)

	if not page_context:
		page_context = make_page_context(path)
		if can_cache(page_context.no_cache):
			page_context_cache[frappe.local.lang] = page_context

			frappe.cache().hset("page_context", path, page_context_cache)

	return page_context

def make_page_context(path):
	context = resolve_route(path)
	if not context:
		raise frappe.DoesNotExistError

	context.doctype = context.ref_doctype
	context.title = context.page_title
	context.pathname = frappe.local.path

	return context

def resolve_route(path):
	"""Returns the page route object based on searching in pages and generators.
	The `www` folder is also a part of generator **Web Page**.

	The only exceptions are `/about` and `/contact` these will be searched in Web Pages
	first before checking the standard pages."""
	if path not in ("about", "contact"):
		context = get_page_context_from_template(path)
		if context:
			return context
		return get_page_context_from_doctype(path)
	else:
		context = get_page_context_from_doctype(path)
		if context:
			return context
		return get_page_context_from_template(path)

def get_page_context_from_template(path):
	'''Return page_info from path'''
	for app in frappe.get_installed_apps():
		app_path = frappe.get_app_path(app)

		folders = frappe.local.flags.web_pages_folders or ('www', 'templates/pages')

		for start in folders:
			search_path = os.path.join(app_path, start, path)
			options = (search_path, search_path + '.html', search_path + '.md',
				search_path + '/index.html', search_path + '/index.md')
			for o in options:
				if os.path.exists(o) and not os.path.isdir(o):
					return get_page_info(o, app, app_path=app_path)

	return None

def get_page_context_from_doctype(path):
	page_info = get_page_info_from_doctypes(path)
	if page_info:
		return frappe.get_doc(page_info.get("doctype"), page_info.get("name")).get_page_info()

def clear_sitemap():
	delete_page_cache("*")

def get_all_page_context_from_doctypes():
	'''Get all doctype generated routes (for sitemap.xml)'''
	routes = frappe.cache().get_value("website_generator_routes")
	if not routes:
		routes = get_page_info_from_doctypes()
		frappe.cache().set_value("website_generator_routes", routes)

	return routes

def get_page_info_from_doctypes(path=None):
	routes = {}
	for app in frappe.get_installed_apps():
		for doctype in frappe.get_hooks("website_generators", app_name = app):
			condition = ""
			values = []
			controller = get_controller(doctype)

			if controller.website.condition_field:
				condition ="where {0}=1".format(controller.website.condition_field)

			if path:
				condition += ' {0} `route`=%s limit 1'.format('and' if 'where' in condition else 'where')
				values.append(path)

			for r in frappe.db.sql("""select route, name, modified from `tab{0}`
					{1}""".format(doctype, condition), values=values, as_dict=True):
				routes[r.route] = {"doctype": doctype, "name": r.name, "modified": r.modified}

				# just want one path, return it!
				if path:
					return routes[r.route]

	return routes

def get_pages():
	'''Get all pages. Called for docs / sitemap'''
	pages = {}
	frappe.local.flags.in_get_all_pages = True

	folders = frappe.local.flags.web_pages_folders or ('www', 'templates/pages')
	apps = frappe.local.flags.web_pages_apps or frappe.get_installed_apps()

	for app in apps:
		app_path = frappe.get_app_path(app)

		for start in folders:
			path = os.path.join(app_path, start)
			pages.update(get_pages_from_path(path, app, app_path))
	frappe.local.flags.in_get_all_pages = False

	return pages

def get_pages_from_path(path, app, app_path):
	pages = {}
	if os.path.exists(path):
		for basepath, folders, files in os.walk(path):
			# add missing __init__.py
			if not '__init__.py' in files:
				open(os.path.join(basepath, '__init__.py'), 'a').close()

			for fname in files:
				fname = frappe.utils.cstr(fname)
				page_name, extn = fname.rsplit(".", 1)
				if extn in ('js', 'css') and os.path.exists(os.path.join(basepath, fname + '.html')):
					# js, css is linked to html, skip
					continue

				if extn in ("html", "xml", "js", "css", "md"):
					page_info = get_page_info(path, app, basepath, app_path, fname)
					pages[page_info.route] = page_info
					# print frappe.as_json(pages[-1])

	return pages

def get_page_info(path, app, basepath=None, app_path=None, fname=None):
	'''Load page info'''
	if not fname:
		fname = os.path.basename(path)

	if not app_path:
		app_path = frappe.get_app_path(app)

	if not basepath:
		basepath = os.path.dirname(path)

	page_name, extn = fname.rsplit(".", 1)

	# add website route
	page_info = frappe._dict()

	page_info.basename = page_name if extn in ('html', 'md') else fname
	page_info.basepath = basepath
	page_info.page_or_generator = "Page"

	page_info.template = os.path.relpath(os.path.join(basepath, fname), app_path)

	if page_info.basename == 'index':
		page_info.basename = ""

	page_info.route = page_info.name = page_info.page_name = os.path.join(os.path.relpath(basepath, path),
		page_info.basename).strip('/.')

	# controller
	page_info.controller_path = os.path.join(basepath, page_name.replace("-", "_") + ".py")

	if os.path.exists(page_info.controller_path):
		controller = app + "." + os.path.relpath(page_info.controller_path,
			app_path).replace(os.path.sep, ".")[:-3]
		page_info.controller = controller

	# get the source
	setup_source(page_info)

	if page_info.only_content:
		# extract properties from HTML comments
		load_properties(page_info)

	return page_info

def setup_source(page_info):
	'''Get the HTML source of the template'''
	from markdown2 import markdown
	jenv = frappe.get_jenv()
	source = jenv.loader.get_source(jenv, page_info.template)[0]
	html = ''

	if page_info.template.endswith('.md'):
		source = markdown(source)

	# if only content
	if page_info.template.endswith('.html') or page_info.template.endswith('.md'):
		if ('</body>' not in source) and ('{% block' not in source):
			page_info.only_content = True
			js, css = '', ''

			js_path = os.path.join(page_info.basepath, page_info.basename + '.js')
			if os.path.exists(js_path):
				js = unicode(open(js_path, 'r').read(), 'utf-8')

			css_path = os.path.join(page_info.basepath, page_info.basename + '.css')
			if os.path.exists(css_path):
				css = unicode(open(css_path, 'r').read(), 'utf-8')

			html = '{% extends "templates/web.html" %}'

			if css:
				html += '\n{% block style %}\n<style>\n' + css + '\n</style>\n{% endblock %}'

			html += '\n{% block page_content %}\n' + source + '\n{% endblock %}'

			if js:
				html += '\n{% block script %}<script>' + js + '\n</script>\n{% endblock %}'
		else:
			html = source

	page_info.source = html

	# show table of contents
	setup_index(page_info)

def setup_index(page_info):
	'''Build page sequence from index.txt'''
	if page_info.basename=='':
		# load index.txt if loading all pages
		index_txt_path = os.path.join(page_info.basepath, 'index.txt')
		if os.path.exists(index_txt_path):
			page_info.index = open(index_txt_path, 'r').read().splitlines()

def make_toc(context, out):
	'''Insert full index (table of contents) for {index} tag'''
	from frappe.website.utils import get_full_index
	if '{index}' in out:
		html = frappe.get_template("templates/includes/full_index.html").render({
			"full_index": get_full_index(),
			"url_prefix": context.url_prefix or "/",
			"route": context.route
		})

		out = out.replace('{index}', html)

	if '{next}' in out:
		# insert next link
		next_item = None
		children_map = get_full_index()
		parent_route = os.path.dirname(context.route)
		children = children_map[parent_route]

		if parent_route and children:
			for i, c in enumerate(children):
				if c.route == context.route and i < (len(children) - 1):
					next_item = children[i+1]
					next_item.url_prefix = context.url_prefix or "/"

		if next_item:
			if next_item.route and next_item.title:
				html = ('<p class="btn-next-wrapper">'+_("Next")\
					+': <a class="btn-next" href="{url_prefix}{route}">{title}</a></p>').format(**next_item)

				out = out.replace('{next}', html)

	return out


def load_properties(page_info):
	'''Load properties like no_cache, title from raw'''
	import re

	if not page_info.title:
		if "<!-- title:" in page_info.source:
			page_info.title = re.findall('<!-- title:([^>]*) -->', page_info.source)[0].strip()
		elif "<h1>" in page_info.source:
			match = re.findall('<h1>([^>]*)</h1>', page_info.source)
			if match:
				page_info.title = match[0].strip()
		else:
			page_info.title = os.path.basename(page_info.name).replace('_', ' ').replace('-', ' ').title()

	if page_info.title and not '{% block title %}' in page_info.source:
		page_info.source += '\n{% block title %}' + page_info.title + '{% endblock %}'

	if "<!-- no-breadcrumbs -->" in page_info.source:
		page_info.no_breadcrumbs = 1

	if "<!-- no-header -->" in page_info.source:
		page_info.no_header = 1
	else:
		# every page needs a header
		# add missing header if there is no <h1> tag
		if (not '{% block header %}' in page_info.source) and (not '<h1' in page_info.source):
			page_info.source += '\n{% block header %}<h1>' + page_info.title + '</h1>{% endblock %}'

	if "<!-- no-cache -->" in page_info.source:
		page_info.no_cache = 1

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
