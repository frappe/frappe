from frappe.website.page_renderers.template_page import TemplatePage


class ErrorPage(TemplatePage):
<<<<<<< HEAD
	def __init__(self, path=None, http_status_code=None, exception=None):
		path = "error"
		super().__init__(path=path, http_status_code=http_status_code)
		self.exception = exception
=======
	def __init__(self, path=None, http_status_code=None, exception=None, title=None, message=None):
		path = "error"
		super().__init__(path=path, http_status_code=http_status_code)
		self.exception = exception
		self.http_status_code = http_status_code
		self.title = title
		self.message = message
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

	def can_render(self):
		return True

	def init_context(self):
		super().init_context()
<<<<<<< HEAD
		self.context.http_status_code = getattr(self.exception, "http_status_code", None) or 500
		self.context.error_title = getattr(self.exception, "title", None)
		self.context.error_message = getattr(self.exception, "message", None)
=======
		self.context.http_status_code = (
			self.http_status_code or getattr(self.exception, "http_status_code", None) or 500
		)
		self.context.title = self.title or getattr(self.exception, "title", None)
		self.context.message = self.message or getattr(self.exception, "message", None)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
