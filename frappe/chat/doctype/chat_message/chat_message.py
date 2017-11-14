# imports - module imports
from   frappe.model.document import Document
from   frappe import _
import frappe

# imports - frappe module imports
from frappe.chat.utils import get_user_doc

session = frappe.session

class ChatMessage(Document):
	pass

@frappe.whitelist()
def send(user, room, content):
	user = get_user_doc(user)

@frappe.whitelist()
def delete():
	pass