import frappe
from frappe.website.page_controllers.template_page import TemplatePage

class PrintPage(TemplatePage):
	'''
	default path returns a printable object (based on permission)
	/Quotation/Q-0001
	'''
	def validate(self):
		parts = self.path.split('/', 1)
		if len(parts)==2:
			if (frappe.db.get_value('DocType', parts[0])
				and frappe.db.get_value(parts[0], parts[1])):
				frappe.form_dict.doctype = parts[0]
				frappe.form_dict.name = parts[1]
				self.set_standard_path('printview')
				return True

		return False
