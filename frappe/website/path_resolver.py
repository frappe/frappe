import re

import click
import werkzeug.routing.exceptions
from werkzeug.routing import Rule

import frappe
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.page_renderers.list_page import ListPage
from frappe.website.page_renderers.not_found_page import NotFoundPage
from frappe.website.page_renderers.print_page import PrintPage
from frappe.website.page_renderers.redirect_page import RedirectPage
from frappe.website.page_renderers.static_page import StaticPage
from frappe.website.page_renderers.template_page import TemplatePage
from frappe.website.page_renderers.web_form import WebFormPage
from frappe.website.router import evaluate_dynamic_routes
from frappe.website.utils import can_cache, get_home_page


class PathResolver:
	__slots__ = ("http_status_code", "path")

	def __init__(self, path, http_status_code=None):
		self.path = path.strip("/ ")
		self.http_status_code = http_status_code

	def resolve(self):
		"""Return endpoint and a renderer instance that can render the endpoint."""
		request = frappe._dict()
		if hasattr(frappe.local, "request"):
			request = frappe.local.request or request

		# WARN: Hardcoded for better performance
		if self.path == "app" or self.path.startswith("app/"):
			return "app", TemplatePage("app", self.http_status_code)

		# check if the request url is in 404 list
		if request.url and can_cache() and frappe.cache.hget("website_404", request.url):
			return self.path, NotFoundPage(self.path)

		try:
			resolve_redirect(self.path, request.query_string)
		except frappe.Redirect as e:
			return frappe.flags.redirect_location, RedirectPage(self.path, e.http_status_code)

		if frappe.get_hooks("website_path_resolver"):
			for handler in frappe.get_hooks("website_path_resolver"):
				endpoint = frappe.get_attr(handler)(self.path)
		else:
			try:
				endpoint = resolve_path(self.path)
			except werkzeug.routing.exceptions.RequestRedirect as e:
				frappe.flags.redirect_location = e.new_url
				return frappe.flags.redirect_location, RedirectPage(e.new_url, e.code)

		custom_renderers = self.get_custom_page_renderers()
		renderers = [
			*custom_renderers,
			StaticPage,
			WebFormPage,
			DocumentPage,
			TemplatePage,
			ListPage,
			PrintPage,
		]

		for renderer in renderers:
			renderer_instance = renderer(endpoint, self.http_status_code)
			if renderer_instance.can_render():
				return endpoint, renderer_instance

		return endpoint, NotFoundPage(endpoint)

	def is_valid_path(self):
		_endpoint, renderer_instance = self.resolve()
		return not isinstance(renderer_instance, NotFoundPage)

	@staticmethod
	def get_custom_page_renderers():
		custom_renderers = []
		for renderer_path in frappe.get_hooks("page_renderer") or []:
			try:
				renderer = frappe.get_attr(renderer_path)
				if not hasattr(renderer, "can_render"):
					click.echo(f"{renderer.__name__} does not have can_render method")
					continue
				if not hasattr(renderer, "render"):
					click.echo(f"{renderer.__name__} does not have render method")
					continue

				custom_renderers.append(renderer)

			except Exception:
				click.echo(f"Failed to load page renderer. Import path: {renderer_path}")

		return custom_renderers


def resolve_redirect(path, query_string=None):
	"""
	Resolve redirects from hooks

	Example:

	                website_redirect = [
	                                # absolute location
	                                {"source": "/from", "target": "https://mysite/from"},

	                                # relative location
	                                {"source": "/from", "target": "/main"},

	                                # use regex
	                                {"source": r"/from/(.*)", "target": r"/main/\1"}
	                                # use r as a string prefix if you use regex groups or want to escape any string literal
	                ]
	"""

	redirect_to = frappe.cache.hget("website_redirects", path or "/")
	if redirect_to:
		if isinstance(redirect_to, dict):
			frappe.flags.redirect_location = redirect_to["path"]
			raise frappe.Redirect(redirect_to["status_code"])
		frappe.flags.redirect_location = redirect_to
		raise frappe.Redirect

	if redirect_to is False:
		return

	redirects = frappe.get_hooks("website_redirects")
	redirects += [
		{"source": r.source, "target": r.target, "redirect_http_status": r.redirect_http_status}
		for r in (frappe.get_website_settings("route_redirects") or [])
	]

	if not redirects:
		return

	for rule in redirects:
		pattern = rule["source"].strip("/ ") + "$"
		path_to_match = path
		if query_string and rule.get("match_with_query_string"):
			path_to_match = path + "?" + frappe.safe_decode(query_string)

		try:
			match = re.match(pattern, path_to_match)
		except re.error:
			frappe.log_error("Broken Redirect: " + pattern)

		if match:
			redirect_to = re.sub(pattern, rule["target"], path_to_match)
			frappe.flags.redirect_location = redirect_to
			status_code = rule.get("redirect_http_status") or 301
			frappe.cache.hset(
				"website_redirects", path_to_match or "/", {"path": redirect_to, "status_code": status_code}
			)
			raise frappe.Redirect(status_code)

	frappe.cache.hset("website_redirects", path_to_match or "/", False)


def resolve_path(path):
	if not path:
		path = "index"

	if path.endswith(".html"):
		path = path[:-5]

	if path == "index":
		path = get_home_page()

	frappe.local.path = path

	if path != "index":
		path = resolve_from_map(path)

	return path


def resolve_from_map(path):
	"""transform dynamic route to a static one from hooks and route defined in doctype"""
	rules = [
		Rule(r["from_route"], endpoint=r["to_route"], defaults=r.get("defaults")) for r in get_website_rules()
	]

	return evaluate_dynamic_routes(rules, path) or path


def get_website_rules():
	"""Get website route rules from hooks and DocType route"""

	def _get():
		rules = frappe.get_hooks("website_route_rules")
		for d in frappe.get_all("DocType", "name, route", dict(has_web_view=1)):
			if d.route:
				rules.append(dict(from_route="/" + d.route.strip("/"), to_route=d.name))

		return rules

	if frappe._dev_server:
		# dont cache in development
		return _get()

	return frappe.cache.get_value("website_route_rules", _get)


def validate_path(path: str):
	if not PathResolver(path).is_valid_path():
		frappe.throw(frappe._("Path {0} it not a valid path").format(frappe.bold(path)))
