import frappe

class WebPage(object):
	def __init__(self, path=None, http_status_code=None):
		self.headers = None
		self.http_status_code = http_status_code or 200
		if not path:
			path = frappe.local.request.path
		self.path = path.strip('/ ')
		self.basepath = None
		self.basename = None
		self.name = None
		self.route = None
		self.file_dir = None

	def can_render(self):
		pass

	def render(self):
		pass

