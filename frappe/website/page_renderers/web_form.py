from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.router import get_page_info_from_web_form


class WebFormPage(DocumentPage):
	def can_render(self):
		web_form = get_page_info_from_web_form(self.path)
		if web_form:
			self.doctype = "Web Form"
			self.docname = web_form.name
			return True
		else:
			return False
