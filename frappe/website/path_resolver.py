import re

from werkzeug.routing import Rule

import frappe
from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
from frappe.website.page_controllers.print_page import PrintPage
from frappe.website.page_controllers.redirect_page import RedirectPage
from frappe.website.page_controllers.static_page import StaticPage
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.page_controllers.web_form import WebFormPage
from frappe.website.router import evaluate_dynamic_routes
from frappe.website.utils import can_cache, get_home_page


class PathResolver():
	def __init__(self, path):
		self.path = path.strip('/ ')

	def resolve(self):
		'''Returns endpoint and a renderer instance that can render the endpoint'''
		request = frappe._dict()
		if hasattr(frappe.local, 'request'):
			request = frappe.local.request or request

		# check if the request url is in 404 list
		if request.url and can_cache() and frappe.cache().hget('website_404', request.url):
			return self.path, NotFoundPage(self.path)

		try:
			resolve_redirect(self.path, request.query_string)
		except frappe.Redirect:
			return self.path, RedirectPage(self.path)

		endpoint = resolve_path(self.path)
		renderers = (StaticPage, WebFormPage, TemplatePage, ListPage, DocumentPage, PrintPage, NotFoundPage)

		for renderer in renderers:
			renderer_instance = renderer(endpoint, 200)
			can_render = renderer_instance.validate()
			if can_render:
				return endpoint, renderer_instance

		return endpoint, NotFoundPage(endpoint)

	def is_valid_path(self):
		_endpoint, renderer_instance = self.resolve()
		return not isinstance(renderer_instance, NotFoundPage)


def resolve_redirect(path, query_string=None):
	'''
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
	'''
	redirects = frappe.get_hooks('website_redirects')
	redirects += frappe.db.get_all('Website Route Redirect', ['source', 'target'])

	if not redirects: return

	redirect_to = frappe.cache().hget('website_redirects', path)

	if redirect_to:
		frappe.flags.redirect_location = redirect_to
		raise frappe.Redirect

	for rule in redirects:
		pattern = rule['source'].strip('/ ') + '$'
		path_to_match = path
		if rule.get('match_with_query_string'):
			path_to_match = path + '?' + frappe.safe_decode(query_string)

		if re.match(pattern, path_to_match):
			redirect_to = re.sub(pattern, rule['target'], path_to_match)
			frappe.flags.redirect_location = redirect_to
			frappe.cache().hset('website_redirects', path_to_match, redirect_to)
			raise frappe.Redirect


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
