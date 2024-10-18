import frappe
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.router import get_page_info_from_web_form


class WebFormPage(DocumentPage):
	def can_render(self):
		web_form = get_page_info_from_web_form(self.path)
		if web_form:
			self.doctype = "Web Form"
			self.docname = web_form.name
			self.set_headers()
			return True
		else:
			return False

	def set_headers(self):
		doc = frappe.get_cached_doc(self.doctype, self.docname)
		allowed_embedding_domains = doc.allowed_embedding_domains
		if allowed_embedding_domains:
			allowed_embedding_domains = allowed_embedding_domains.replace("\n", " ")
			self.headers = {"Content-Security-Policy": f"frame-ancestors 'self' {allowed_embedding_domains}"}
