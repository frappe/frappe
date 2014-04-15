# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import mimetypes, json
from werkzeug.wrappers import Response

from frappe.website.context import get_context
from frappe.website.utils import scrub_relative_urls, get_home_page, can_cache
from frappe.website.permissions import get_access, clear_permissions

class PageNotFoundError(Exception): pass

def render(path, http_status_code=None):
	"""render html page"""
	path = resolve_path(path.lstrip("/"))

	try:
		data = render_page(path)

	except frappe.DoesNotExistError, e:
		path = "404"
		data = render_page(path)
		http_status_code = e.http_status_code

	except Exception:
		path = "error"
		data = render_page(path)
		http_status_code = 500

	return build_response(path, data, http_status_code or 200)

def build_response(path, data, http_status_code):
	# build response
	response = Response()
	response.data = set_content_type(response, data, path)
	response.status_code = http_status_code
	response.headers[b"X-Page-Name"] = path.encode("utf-8")
	response.headers[b"X-From-Cache"] = frappe.local.response.from_cache or False
	return response

def render_page(path):
	"""get page html"""
	cache_key = ("page_context:{}" if is_ajax() else "page:{}").format(path)

	out = None

	# try memcache
	if can_cache():
		out = frappe.cache().get_value(cache_key)
		if out and is_ajax():
			out = out.get("data")

	if out:
		frappe.local.response.from_cache = True
		return out

	return build(path)

def build(path):
	if not frappe.db:
		frappe.connect()

	build_method = (build_json if is_ajax() else build_page)

	try:
		return build_method(path)
	except frappe.DoesNotExistError:
		hooks = frappe.get_hooks()
		if hooks.website_catch_all:
			path = hooks.website_catch_all[0]
			return build_method(path)
		else:
			raise

def build_json(path):
	return get_context(path).data

def build_page(path):
	context = get_context(path)

	html = frappe.get_template(context.base_template_path).render(context)
	html = scrub_relative_urls(html)

	if can_cache(context.no_cache):
		frappe.cache().set_value("page:" + path, html)

	return html

def is_ajax():
	return getattr(frappe.local, "is_ajax")

def resolve_path(path):
	if not path:
		path = "index"

	if path.endswith('.html'):
		path = path[:-5]

	if path == "index":
		path = get_home_page()

	return path

def set_content_type(response, data, path):
	if isinstance(data, dict):
		response.headers[b"Content-Type"] = b"application/json; charset: utf-8"
		data = json.dumps(data)
		return data

	response.headers[b"Content-Type"] = b"text/html; charset: utf-8"

	if "." in path:
		content_type, encoding = mimetypes.guess_type(path)
		if not content_type:
			raise frappe.UnsupportedMediaType("Cannot determine content type of {}".format(path))
		response.headers[b"Content-Type"] = content_type.encode("utf-8")

	return data

def clear_cache(path=None):
	cache = frappe.cache()

	if path:
		delete_page_cache(path)

	else:
		for p in frappe.db.sql_list("""select name from `tabWebsite Route`"""):
			if p is not None:
				delete_page_cache(p)

		cache.delete_value("home_page")
		clear_permissions()

	for method in frappe.get_hooks("website_clear_cache"):
		frappe.get_attr(method)(path)

def delete_page_cache(path):
	cache = frappe.cache()
	cache.delete_value("page:" + path)
	cache.delete_value("page_context:" + path)
	cache.delete_value("sitemap_options:" + path)
