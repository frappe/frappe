from frappe import _
from frappe.website.page_controllers.template_page import TemplatePage

class NotFoundPage(TemplatePage):
	def __init__(self, path, http_status_code):
		super().__init__(path=path, http_status_code=http_status_code)
		self.path = '404'
		self.http_status_code = 404
		self.template_path = '404'
