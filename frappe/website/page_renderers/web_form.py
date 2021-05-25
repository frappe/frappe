from frappe.website.page_renderers.web_page import WebPage
import frappe

class WebFormPage(WebPage):
	def can_render(self):
		return bool(frappe.get_all("Web Form", filters={'route': self.path}))
