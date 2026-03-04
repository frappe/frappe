import frappe
from frappe.modules import load_doctype_module
from frappe.website.page_renderers.template_page import TemplatePage


class ListPage(TemplatePage):
	def can_render(self):
		doctype = self.path
		if not doctype or doctype == "Web Page":
			return False

		try:
			meta = frappe.get_meta(doctype)
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			return False

		if meta.has_web_view:
			return True

		if meta.custom:
			return False

		module = load_doctype_module(doctype)
		return hasattr(module, "get_list_context")

	def render(self):
		frappe.form_dict.doctype = self.path
		self.set_standard_path("portal")
		return super().render()
