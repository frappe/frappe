import mimetypes
import os

from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

import frappe
from frappe.website.page_controllers.web_page import WebPage

UNSUPPORTED_STATIC_PAGE_TYPES = ('html', 'md', 'js', 'xml', 'css', 'txt', 'py', 'json')

class StaticPage(WebPage):
	def __init__(self, path, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.set_file_path()

	def set_file_path(self):
		self.file_path = ''
		if not self.is_valid_file_path():
			return
		for app in frappe.get_installed_apps():
			file_path = frappe.get_app_path(app, 'www') + '/' + self.path
			if os.path.exists(file_path):
				self.file_path = file_path

	def validate(self):
		return self.is_valid_file_path() and self.file_path

	def is_valid_file_path(self):
		if ('.' not in self.path):
			return False
		extension = self.path.rsplit('.', 1)[-1]
		if extension in UNSUPPORTED_STATIC_PAGE_TYPES:
			return False
		return True

	def render(self):
		f = open(self.file_path, 'rb')
		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
		response.mimetype = mimetypes.guess_type(self.file_path)[0] or 'application/octet-stream'
		return response
