from frappe.website.page_controllers.template_page import TemplatePage

class NotFoundPage(TemplatePage):
	def __init__(self, path, http_status_code):
		path = '404'
		http_status_code = 404
		super().__init__(path=path, http_status_code=http_status_code)

	def validate(self):
		return True
