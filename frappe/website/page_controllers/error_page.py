from frappe.website.page_controllers.template_page import TemplatePage

class ErrorPage(TemplatePage):
	def __init__(self, path, http_status_code, exception):
		path = 'error'
		super().__init__(path=path, http_status_code=http_status_code)
		self.http_status_code = getattr(exception, 'http_status_code', None) or http_status_code or 500
