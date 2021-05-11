import frappe
from frappe import _
from frappe.website.page_controllers.template_page import TemplatePage

class NotPermittedPage(TemplatePage):
	def __init__(self, path, http_status_code):
		super().__init__(path=path, http_status_code=http_status_code)
		self.http_status_code = 403

	def validate(self):
		frappe.local.message_title = _("Not Permitted")
		frappe.local.response['context'] = dict(
			indicator_color = 'red',
			primary_action = '/login',
			primary_label = _('Login'),
			fullpage=True
		)
		self.set_standard_path('message')
		return True
