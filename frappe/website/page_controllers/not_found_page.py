import frappe
from frappe.website.page_controllers.template_page import TemplatePage
from frappe.website.utils import can_cache
from urllib.parse import urlparse

HOMEPAGE_PATHS = ('/', '/index', '', 'index')

class NotFoundPage(TemplatePage):
	def __init__(self, path, http_status_code):
		self.resolved_path = path
		path = '404'
		http_status_code = 404
		super().__init__(path=path, http_status_code=http_status_code)

	def validate(self):
		return True

	def render(self):
		if can_cache_404(self.resolved_path):
			frappe.cache().hset('website_404', frappe.request.url, True)
		return super().render()

def can_cache_404(path):
	# do not cache 404 for custom homepages
	return can_cache() and not is_custom_home_page(path)

def is_custom_home_page(path):
	url = frappe.request.url
	url_parts = urlparse(url)
	return url_parts.path in HOMEPAGE_PATHS and path not in HOMEPAGE_PATHS
