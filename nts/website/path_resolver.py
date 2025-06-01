import re

import click
import werkzeug.routing.exceptions
from werkzeug.routing import Rule

import nts
from nts.website.page_renderers.document_page import DocumentPage
from nts.website.page_renderers.list_page import ListPage
from nts.website.page_renderers.not_found_page import NotFoundPage
from nts.website.page_renderers.print_page import PrintPage
from nts.website.page_renderers.redirect_page import RedirectPage
from nts.website.page_renderers.static_page import StaticPage
from nts.website.page_renderers.template_page import TemplatePage
from nts.website.page_renderers.web_form import WebFormPage
from nts.website.router import evaluate_dynamic_routes
from nts.website.utils import can_cache, get_home_page


class PathResolver:
	__slots__ = ("path", "http_status_code")

	def __init__(self, path, http_status_code=None):
		self.path = path.strip("/ ")
		self.http_status_code = http_status_code

	def resolve(self):
		"""Returns endpoint and a renderer instance that can render the endpoint"""
		request = nts._dict()
		if hasattr(nts.local, "request"):
			request = nts.local.request or request

		# check if the request url is in 404 list
		if request.url and can_cache() and nts.cache.hget("website_404", request.url):
			return self.path, NotFoundPage(self.path)

		try:
			resolve_redirect(self.path, request.query_string)
		except nts.Redirect as e:
			return nts.flags.redirect_location, RedirectPage(self.path, e.http_status_code)

		if nts.get_hooks("website_path_resolver"):
			for handler in nts.get_hooks("website_path_resolver"):
				endpoint = nts.get_attr(handler)(self.path)
		else:
			try:
				endpoint = resolve_path(self.path)
			except werkzeug.routing.exceptions.RequestRedirect as e:
				nts.flags.redirect_location = e.new_url
				return nts.flags.redirect_location, RedirectPage(e.new_url, e.code)

		# WARN: Hardcoded for better performance
		if endpoint == "app":
			return endpoint, TemplatePage(endpoint, self.http_status_code)

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
		for renderer_path in nts.get_hooks("page_renderer") or []:
			try:
				renderer = nts.get_attr(renderer_path)
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
	redirects = nts.get_hooks("website_redirects")
	redirects += nts.get_all(
		"Website Route Redirect", ["source", "target", "redirect_http_status"], order_by=None
	)

	if not redirects:
		return

	redirect_to = nts.cache.hget("website_redirects", path)

	if redirect_to:
		if isinstance(redirect_to, dict):
			nts.flags.redirect_location = redirect_to["path"]
			raise nts.Redirect(redirect_to["status_code"])
		nts.flags.redirect_location = redirect_to
		raise nts.Redirect

	for rule in redirects:
		pattern = rule["source"].strip("/ ") + "$"
		path_to_match = path
		if query_string and rule.get("match_with_query_string"):
			path_to_match = path + "?" + nts.safe_decode(query_string)

		try:
			match = re.match(pattern, path_to_match)
		except re.error:
			nts.log_error("Broken Redirect: " + pattern)

		if match:
			redirect_to = re.sub(pattern, rule["target"], path_to_match)
			nts.flags.redirect_location = redirect_to
			status_code = rule.get("redirect_http_status") or 301
			nts.cache.hset(
				"website_redirects", path_to_match, {"path": redirect_to, "status_code": status_code}
			)
			raise nts.Redirect(status_code)


def resolve_path(path):
	if not path:
		path = "index"

	if path.endswith(".html"):
		path = path[:-5]

	if path == "index":
		path = get_home_page()

	nts.local.path = path

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
		rules = nts.get_hooks("website_route_rules")
		for d in nts.get_all("DocType", "name, route", dict(has_web_view=1)):
			if d.route:
				rules.append(dict(from_route="/" + d.route.strip("/"), to_route=d.name))

		return rules

	if nts.local.dev_server:
		# dont cache in development
		return _get()

	return nts.cache.get_value("website_route_rules", _get)


def validate_path(path: str):
	if not PathResolver(path).is_valid_path():
		nts.throw(nts._("Path {0} it not a valid path").format(nts.bold(path)))
