from frappe.website.redirect import resolve_redirect
from frappe.website.render import resolve_path
import frappe

from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
from frappe.website.page_controllers.print_page import PrintPage
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.page_controllers.static_page import StaticPage
from frappe.website.page_controllers.web_form import WebFormPage

class PathResolver():
	def __init__(self, path, http_status_code=None):
		self._path = path
		self.http_status_code = http_status_code
		# self.url_map = get_url_map()

	@property
	def path(self):
		return self._path.strip('/ ')

	def resolve(self):
		'''Returns endpoint and a renderer instance that can render the endpoint'''
		query_string = frappe.local.request.query_string
		resolve_redirect(self.path, query_string)
		endpoint = resolve_path(self.path)
		# urls = self.url_map.bind_to_environ(frappe.local.request.environ)

		renderers = (StaticPage, WebFormPage, TemplatePage, ListPage, DocumentPage, PrintPage, NotFoundPage)

		for renderer in renderers:
			renderer_instance = renderer(endpoint, self.http_status_code)
			can_render = renderer_instance.validate()
			if can_render:
				return endpoint, renderer_instance

		return endpoint, None

# #> Path > Path 		> resolve using url_map > path.endpoint
# #
# #
# #
# # 		pathclass	  url_map

# def get_url_map():
# 	Map([Rule('/', endpoint=get_home_page, defaults={'renderer': TemplatePage})])


# query_string = None
# 	response = None

# 	if not path:
# 		path = frappe.local.request.path
# 		query_string = frappe.local.request.query_string

# 	try:
# 		path = path.strip('/ ')
# 		resolve_redirect(path, query_string)
# 		path = resolve_path(path)
# 		# there is no way to determine the type of the page based on the route
# 		# so evaluate each type of page sequentially
# 		renderers = [StaticPage, WebFormPage, TemplatePage, ListPage, DocumentPage, PrintPage, NotFoundPage]
# 		for renderer in renderers:
# 			response = renderer(path, http_status_code).get()
# 			if response:
# 				break
