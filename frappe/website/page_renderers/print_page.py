import frappe
from frappe.website.page_renderers.template_page import TemplatePage


class PrintPage(TemplatePage):
	"""
	default path returns a printable object (based on permission)
	/Quotation/Q-0001
	"""

	def can_render(self):
		parts = self.path.split("/", 1)
		if len(parts) == 2:
			if frappe.db.exists("DocType", parts[0], True) and frappe.db.exists(parts[0], parts[1], True):
				return True

		return False

	def render(self):
		parts = self.path.split("/", 1)
		frappe.form_dict.doctype = parts[0]
		frappe.form_dict.name = parts[1]

		print_format = frappe.form_dict.get("format")
		if print_format is not None and frappe.db.get_value("Print Format", print_format, "print_format_builder_beta"):
			frappe.form_dict.print_format = print_format
			self.set_standard_path("printpreview")
		else:
			self.set_standard_path("printview")
		return super().render()
