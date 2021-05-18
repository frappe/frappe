import frappe

from frappe.website.page_controllers.error_page import ErrorPage
from frappe.website.page_controllers.not_permitted_page import NotPermittedPage
from frappe.website.page_controllers.redirect_page import RedirectPage
from frappe.website.path_resolver import PathResolver
from frappe.website.utils import can_cache

def get_response(path=None, http_status_code=200):
	"""Resolves path and renders page"""
	response = None
	path = path or frappe.local.request.path
	endpoint = path
	# if can_cache():
	# 	# return rendered page
	# 	page_cache = frappe.cache().hget("website_page", path)
	# 	if page_cache and frappe.local.lang in page_cache:
	# 		out = page_cache[frappe.local.lang]

	# if out:
	# 	frappe.local.response.from_cache = True
	# 	return out

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
	return response.data
