import frappe
from frappe.website.page_renderers.template_page import TemplatePage


class PrintPage(TemplatePage):
	"""
	default path returns a printable object (based on permission)
	/Quotation/Q-0001
	"""

	def can_render(self):
		parts = self.path.split("/", 1)
		return len(parts) == 2 and frappe.db.exists("DocType", parts[0], True) == parts[0]

	def render(self):
		parts = self.path.split("/", 1)
		frappe.form_dict.doctype = parts[0]
		frappe.form_dict.name = parts[1]
		self.set_standard_path("printview")
		return super().render()
