import frappe
from frappe.utils import cstr

from frappe.website.page_controllers.document_page import DocumentPage
from frappe.website.page_controllers.error_page import ErrorPage
from frappe.website.page_controllers.list_page import ListPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
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
	response = None

	if not path:
		path = frappe.local.request.path
		query_string = frappe.local.request.query_string

	try:
		path = path.strip('/ ')
		resolve_redirect(path, query_string)
		path = resolve_path(path)
		# there is no way to determine the type of the page based on the route
		# so evaluate each type of page sequentially
		renderers = [StaticPage, WebFormPage, TemplatePage, ListPage, DocumentPage, PrintPage, NotFoundPage]
		for renderer in renderers:
			response = renderer(path, http_status_code).get()
			if response:
				break
	except frappe.Redirect:
		return build_response(path, "", 301, {
			"Location": frappe.flags.redirect_location or (frappe.local.response or {}).get('location'),
			"Cache-Control": "no-store, no-cache, must-revalidate"
		})
	except frappe.PermissionError as e:
		frappe.local.message = cstr(e)
		response = NotPermittedPage(path, http_status_code).get()
	except Exception as e:
		response = ErrorPage(path, http_status_code, exception=e).get()

	return response
