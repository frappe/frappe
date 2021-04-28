import frappe
from frappe.utils import cstr

from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_permitted_page import NotPermittedPage
from frappe.website.page_controllers.print_page import PrintPage
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.page_controllers.static_page import StaticPage
from frappe.website.page_controllers.web_form import WebFormPage

from frappe.website.redirect import resolve_redirect
from frappe.website.render import build_response, resolve_path

def get_response(path=None, http_status_code=200):
	"""render html page"""
	query_string = None
	if not path:
		path = frappe.local.request.path
		query_string = frappe.local.request.query_string

	try:
		path = path.strip('/ ')
		resolve_redirect(path, query_string)
		path = resolve_path(path)

		# there is no way to determine the type of the page based on the route
		# so evaluate each type of page sequentially
		response = StaticPage(path, http_status_code).get()
		if not response:
			response = TemplatePage(path, http_status_code).get()
		if not response:
			response = ListPage(path, http_status_code).get()
		if not response:
			response = WebFormPage(path, http_status_code).get()
		if not response:
			response = DocumentPage(path, http_status_code).get()
		if not response:
			response = PrintPage(path, http_status_code).get()
		if not response:
			response = TemplatePage('404', 404).get()
	except frappe.Redirect:
		return build_response(path, "", 301, {
			"Location": frappe.flags.redirect_location or (frappe.local.response or {}).get('location'),
			"Cache-Control": "no-store, no-cache, must-revalidate"
		})
	except frappe.PermissionError as e:
		frappe.local.message = cstr(e)
		response = NotPermittedPage(path, http_status_code).get()
	except Exception as e:
		response = TemplatePage('error', getattr(e, 'http_status_code', None) or http_status_code).get()

	return response
