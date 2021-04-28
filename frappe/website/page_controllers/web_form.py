from frappe.website.page_controllers.web_page import WebPage
import frappe

class WebFormPage(WebPage):
	def validate(self):
		return bool(frappe.get_all("Web Form", filters={'route': self.path}))
