import frappe
from frappe.website.utils import build_response


class BaseRenderer:
	def __init__(self, path=None, http_status_code=None):
		self.headers = None
		self.http_status_code = http_status_code or 200
		if not path:
			path = frappe.local.request.path
		self.path = path.strip("/ ")
		self.basepath = ""
		self.basename = ""
		self.name = ""
		self.route = ""
		self.file_dir = None

	def can_render(self):
		raise NotImplementedError

	def render(self):
		raise NotImplementedError

	def build_response(self, data, http_status_code=None, headers=None):
		return build_response(
			self.path, data, http_status_code or self.http_status_code, headers or self.headers
		)
