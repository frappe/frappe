from frappe.website.page_renderers.template_page import TemplatePage

class ErrorPage(TemplatePage):
	def __init__(self, path=None, http_status_code=None, exception=None):
		path = 'error'
		super().__init__(path=path, http_status_code=http_status_code)
		self.http_status_code = getattr(exception, 'http_status_code', None) or http_status_code or 500

	def can_render(self):
		return True
