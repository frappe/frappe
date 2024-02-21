from frappe.website.page_renderers.template_page import TemplatePage


class ErrorPage(TemplatePage):
	def __init__(self, path=None, http_status_code=None, exception=None):
		path = "error"
		super().__init__(path=path, http_status_code=http_status_code)
		self.exception = exception

	def can_render(self):
		return True

	def init_context(self):
		super().init_context()
		self.context.http_status_code = getattr(self.exception, "http_status_code", None) or 500
		self.context.error_title = getattr(self.exception, "title", None)
		self.context.error_message = getattr(self.exception, "message", None)
