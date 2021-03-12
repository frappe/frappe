import frappe
from frappe import _
from frappe.website.page_controllers.template_page import TemplatePage

class NotPermittedPage(TemplatePage):
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
