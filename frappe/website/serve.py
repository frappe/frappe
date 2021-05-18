import frappe
from frappe.website.page_controllers.error_page import ErrorPage
from frappe.website.page_controllers.not_found_page import NotFoundPage
from frappe.website.page_controllers.not_permitted_page import NotPermittedPage
from frappe.website.page_controllers.redirect_page import RedirectPage
from frappe.website.path_resolver import PathResolver
from frappe.website.utils import can_cache


def get_response(path=None, http_status_code=200):
	"""Resolves path and renders page"""
	response = None
	path = path or frappe.local.request.path
	endpoint = path

	if can_cache() and frappe.cache().hget('website_404', frappe.request.url):
		response = NotFoundPage(path=path).render()
		return response

	try:
		path_resolver = PathResolver(path, http_status_code)
		endpoint, renderer_instance = path_resolver.resolve()
		if renderer_instance:
			response = renderer_instance.render()
	except frappe.Redirect:
		return RedirectPage(endpoint or path, http_status_code).render()
	except frappe.PermissionError as e:
		response = NotPermittedPage(endpoint, http_status_code, exception=e).render()
	except Exception as e:
		response = ErrorPage(exception=e).render()

	return response

def get_response_content(path=None, http_status_code=200):
	response = get_response(path, http_status_code)
	return str(response.data, 'utf-8')
