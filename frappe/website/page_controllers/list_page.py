import frappe
from frappe.website.page_controllers.template_page import TemplatePage

class ListPage(TemplatePage):
	def validate(self):
		if frappe.db.get_value('DocType', self.path):
			frappe.local.form_dict.doctype = self.path
			self.set_standard_path('list')
			return True
		return False
