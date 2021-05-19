import frappe
from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
from frappe.website.page_controllers.print_page import PrintPage
from frappe.website.page_controllers.static_page import StaticPage
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.page_controllers.web_form import WebFormPage
from frappe.website.page_controllers.redirect_page import RedirectPage
from frappe.website.redirect import resolve_redirect
from frappe.website.render import resolve_path
from frappe.website.utils import can_cache


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

