import frappe
from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
from frappe.website.page_controllers.print_page import PrintPage
from frappe.website.page_controllers.static_page import StaticPage
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.page_controllers.web_form import WebFormPage
from frappe.website.redirect import resolve_redirect
from frappe.website.render import resolve_path
from frappe.website.utils import can_cache


class PathResolver():
	def __init__(self, path, http_status_code=None):
		self._path = path
		self.http_status_code = http_status_code

	@property
	def path(self):
		return self._path.strip('/ ')

	def resolve(self):
		'''Returns endpoint and a renderer instance that can render the endpoint'''
		request = frappe._dict()
		if hasattr(frappe.local, 'request'):
			request = frappe.local.request or request

		# check if the request url is in 404 list
		if request.url and can_cache() and frappe.cache().hget('website_404', request.url):
			return self.path, NotFoundPage(self.path)

		resolve_redirect(self.path, request.query_string)
		endpoint = resolve_path(self.path)

		renderers = (StaticPage, WebFormPage, TemplatePage, ListPage, DocumentPage, PrintPage, NotFoundPage)

		for renderer in renderers:
			renderer_instance = renderer(endpoint, self.http_status_code)
			can_render = renderer_instance.validate()
			if can_render:
				return endpoint, renderer_instance

		return endpoint, None
