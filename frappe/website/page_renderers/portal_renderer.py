import frappe
from frappe.website.page_renderers.template_page import TemplatePage
from frappe.website.utils import check_if_webform_exists


class PortalPage(TemplatePage):
	def can_render(self):
		parts = self.path.split("/", 1)
		if len(parts) >= 2:
			menu_item = frappe.db.exists(
				"Portal Menu Item",
				{"route": f"/{parts[1]}"},
			)

			if check_if_webform_exists(parts[1]):
				return False

			if parts[0] == "portal" and menu_item:
				self.ref_doctype = frappe.db.get_value(
					"Portal Menu Item",
					menu_item,
					"reference_doctype",
				)
				return self.ref_doctype

		return False

	def render(self):
		frappe.form_dict.doctype = self.ref_doctype
		self.set_standard_path("portal")
		return super().render()
