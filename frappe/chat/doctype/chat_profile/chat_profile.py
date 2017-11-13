# imports - module imports
import frappe
from frappe.model.document import Document
from frappe import _

class ChatProfile(Document):
	pass

@frappe.whitelist()
def get_chat_profile(user = None):
	user 	= user or frappe.session.user
	


