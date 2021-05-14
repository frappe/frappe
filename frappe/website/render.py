# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.sessions
from frappe.utils import cstr
import os, mimetypes, json
import re

import six
from six import iteritems
from werkzeug.wrappers import Response
from werkzeug.routing import Rule
from werkzeug.wsgi import wrap_file

from frappe.website.context import get_context
from frappe.website.redirect import resolve_redirect
from frappe.website.utils import (get_home_page, can_cache, delete_page_cache,
	get_toc, get_next_link)
from frappe.website.router import clear_sitemap, evaluate_dynamic_routes
from frappe.translate import guess_language

class PageNotFoundError(Exception): pass

def render(path=None, http_status_code=None):
	from frappe.website.serve import get_response
	return get_response(path, http_status_code)

def build_response(path, data, http_status_code, headers=None):
	# build response
	response = Response()
	response.data = set_content_type(response, data, path)
	response.status_code = http_status_code
	response.headers["X-Page-Name"] = path.encode("ascii", errors="xmlcharrefreplace")
	response.headers["X-From-Cache"] = frappe.local.response.from_cache or False

	add_preload_headers(response)
	if headers:
		for key, val in iteritems(headers):
			response.headers[key] = val.encode("ascii", errors="xmlcharrefreplace")

	return response


def add_preload_headers(response):
	from bs4 import BeautifulSoup

	try:
		preload = []
		soup = BeautifulSoup(response.data, "lxml")
		for elem in soup.find_all('script', src=re.compile(".*")):
			preload.append(("script", elem.get("src")))

		for elem in soup.find_all('link', rel="stylesheet"):
			preload.append(("style", elem.get("href")))

		links = []
		for _type, link in preload:
			links.append("<{}>; rel=preload; as={}".format(link, _type))

		if links:
			response.headers["Link"] = ",".join(links)
	except Exception:
		import traceback
		traceback.print_exc()


def render_page(path):
	"""get page html"""
	out = None

	if can_cache():
		# return rendered page
		page_cache = frappe.cache().hget("website_page", path)
		if page_cache and frappe.local.lang in page_cache:
			out = page_cache[frappe.local.lang]

	if out:
		frappe.local.response.from_cache = True
		return out

	return build(path)

def build(path):
	if not frappe.db:
		frappe.connect()

	try:
		return build_page(path)
	except frappe.DoesNotExistError:
		hooks = frappe.get_hooks()
		if hooks.website_catch_all:
			path = hooks.website_catch_all[0]
			return build_page(path)
		else:
			raise
	except Exception:
		raise

def build_page(path):
	if not getattr(frappe.local, "path", None):
		frappe.local.path = path

	context = get_context(path)

	if context.source:
		html = frappe.render_template(context.source, context)
	elif context.template:
		if path.endswith('min.js'):
			html = frappe.get_jloader().get_source(frappe.get_jenv(), context.template)[0]
		else:
			html = frappe.get_template(context.template).render(context)

	if '{index}' in html:
		html = html.replace('{index}', get_toc(context.route))

	if '{next}' in html:
		html = html.replace('{next}', get_next_link(context.route))

	# html = frappe.get_template(context.base_template_path).render(context)

	if can_cache(context.no_cache):
		page_cache = frappe.cache().hget("website_page", path) or {}
		page_cache[frappe.local.lang] = html
		frappe.cache().hset("website_page", path, page_cache)

	return html

def resolve_path(path):
	if not path:
		path = "index"

	if path.endswith('.html'):
		path = path[:-5]

	if path == "index":
		path = get_home_page()

	frappe.local.path = path

	if path != "index":
		path = resolve_from_map(path)

	return path

def resolve_from_map(path):
	'''transform dynamic route to a static one from hooks and route defined in doctype'''
	rules = [Rule(r["from_route"], endpoint=r["to_route"], defaults=r.get("defaults"))
		for r in get_website_rules()]

	return evaluate_dynamic_routes(rules, path) or path

def get_website_rules():
	'''Get website route rules from hooks and DocType route'''
	def _get():
		rules = frappe.get_hooks("website_route_rules")
		for d in frappe.get_all('DocType', 'name, route', dict(has_web_view=1)):
			if d.route:
				rules.append(dict(from_route = '/' + d.route.strip('/'), to_route=d.name))

		return rules

	if frappe.local.dev_server:
		# dont cache in development
		return _get()

	return frappe.cache().get_value('website_route_rules', _get)

def set_content_type(response, data, path):
	if isinstance(data, dict):
		response.mimetype = 'application/json'
		response.charset = 'utf-8'
		data = json.dumps(data)
		return data

	response.mimetype = 'text/html'
	response.charset = 'utf-8'

	if "." in path:
		content_type, encoding = mimetypes.guess_type(path)
		if content_type:
			response.mimetype = content_type
			if encoding:
				response.charset = encoding

	return data

def clear_cache(path=None):
	'''Clear website caches
	:param path: (optional) for the given path'''
	for key in ('website_generator_routes', 'website_pages',
		'website_full_index', 'sitemap_routes'):
		frappe.cache().delete_value(key)

	frappe.cache().delete_value("website_404")
	if path:
		frappe.cache().hdel('website_redirects', path)
		delete_page_cache(path)
	else:
		clear_sitemap()
		frappe.clear_cache("Guest")
		for key in ('portal_menu_items', 'home_page', 'website_route_rules',
			'doctypes_with_web_view', 'website_redirects', 'page_context',
			'website_page'):
			frappe.cache().delete_value(key)

	for method in frappe.get_hooks("website_clear_cache"):
		frappe.get_attr(method)(path)
