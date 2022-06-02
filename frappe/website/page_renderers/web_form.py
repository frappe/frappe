import frappe
from frappe.website.page_renderers.document_page import DocumentPage


class WebFormPage(DocumentPage):
	def can_render(self):
		webform_name = frappe.db.exists("Web Form", {"route": self.path, "published": 1}, cache=True)
		if webform_name:
			self.doctype = "Web Form"
			self.docname = webform_name
		return bool(webform_name)
