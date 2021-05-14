# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import json
import mimetypes
import re

from six import iteritems
from werkzeug.routing import Rule
from werkzeug.wrappers import Response

import frappe
import frappe.sessions
from frappe.website.context import get_context
from frappe.website.router import evaluate_dynamic_routes
from frappe.website.utils import (can_cache, get_home_page, get_next_link, get_toc)


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
	# TODO: Remove this
	from frappe.website.utils import clear_cache
	return clear_cache(path)
