# imports - module imports
import frappe
from   frappe.model.document import Document

class ChatRoom(Document):
	def on_update(self):
		frappe.publish_realtime('chat:room:update', dict(
			type 	  = self.type,
			name      = self.name,
			room_name = self.room_name,
		))

@frappe.whitelist()
def create(kind, name = ''):
	doc	= frappe.new_doc('Chat Room')
	doc.type = kind
	doc.room_name = name
	
	doc.insert()

@frappe.whitelist()
def get(name = None):
	if not name:
		resp = frappe.get_all('Chat Room')
	else:
		resp = frappe.get_doc('Chat Room', name)

	return resp