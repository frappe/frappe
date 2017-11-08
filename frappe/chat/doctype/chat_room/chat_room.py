# imports - module imports
import frappe
from   frappe.model.document import Document

class ChatRoom(Document):
	pass

@frappe.whitelist()
def create(kind, name = ''):
	doc	= frappe.new_doc('Chat Room')
	doc.type = kind
	doc.name = name
	
	doc.insert()

@frappe.whitelist()
def get():
	docs = frappe.get_all('Chat Room')

	return docs