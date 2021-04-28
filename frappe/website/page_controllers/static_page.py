import mimetypes
import os

from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

import frappe
from frappe.website.page_controllers.web_page import WebPage


class StaticPage(WebPage):
	def validate(self):
		if ('.' not in self.path):
			return False
		extension = self.path.rsplit('.', 1)[-1]
		if extension in ('html', 'md', 'js', 'xml', 'css', 'txt', 'py', 'json'):
			return False

		if self.find_path_in_apps():
			return True

		return False

	def find_path_in_apps(self):
		for app in frappe.get_installed_apps():
			file_path = frappe.get_app_path(app, 'www') + '/' + self.path
			if os.path.exists(file_path):
				self.file_path = file_path
				return True
		return False

	def render(self):
		f = open(self.file_path, 'rb')
		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
		response.mimetype = mimetypes.guess_type(self.file_path)[0] or 'application/octet-stream'
		return response
