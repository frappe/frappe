import mimetypes
import os

from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.utils import is_binary_file

UNSUPPORTED_STATIC_PAGE_TYPES = (
	"css",
	"html",
	"js",
	"json",
	"md",
	"py",
	"pyc",
	"pyo",
	"txt",
	"xml",
)


class StaticPage(BaseRenderer):
	__slots__ = ("file_path", "path")

	def __init__(self, path, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.set_file_path()

	def set_file_path(self):
		self.file_path = ""
		if not self.is_valid_file_path():
			return
		for app in frappe.get_installed_apps():
			file_path = frappe.get_app_path(app, "www") + "/" + self.path
			if os.path.isfile(file_path) and is_binary_file(file_path):
				self.file_path = file_path

	def can_render(self):
		return self.is_valid_file_path() and self.file_path

	def is_valid_file_path(self):
		extension = self.path.rsplit(".", 1)[-1] if "." in self.path else ""
		if extension in UNSUPPORTED_STATIC_PAGE_TYPES:
			return False
		return True

	def render(self):
		# file descriptor to be left open, closed by middleware
		f = open(self.file_path, "rb")
		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
		response.mimetype = mimetypes.guess_type(self.file_path)[0] or "application/octet-stream"
		return response
