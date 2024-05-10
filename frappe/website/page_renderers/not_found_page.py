import os
from urllib.parse import urlparse

import frappe
from frappe.website.page_renderers.template_page import TemplatePage
from frappe.website.utils import can_cache

HOMEPAGE_PATHS = ("/", "/index", "index")


class NotFoundPage(TemplatePage):
	def __init__(self, path, http_status_code=None):
		self.request_path = path
		self.request_url = frappe.local.request.url if hasattr(frappe.local, "request") else ""
		path = "404"
		http_status_code = http_status_code or 404
		super().__init__(path=path, http_status_code=http_status_code)

	def can_render(self):
		return True

	def render(self):
		if self.can_cache_404():
			frappe.cache.hset("website_404", self.request_url, True)
		return super().render()

	def can_cache_404(self):
		# do not cache 404 for custom homepages
		return can_cache() and self.request_url and not self.is_custom_home_page()

	def is_custom_home_page(self):
		url_parts = urlparse(self.request_url)
		request_url = os.path.splitext(url_parts.path)[0]
		request_path = os.path.splitext(self.request_path)[0]
		return request_url in HOMEPAGE_PATHS and request_path not in HOMEPAGE_PATHS
