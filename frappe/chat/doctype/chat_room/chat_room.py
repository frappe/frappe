# imports - module imports
import frappe
from frappe.model.document import Document
from frappe import _

class ChatRoom(Document):
	def validate(self):
		if self.type == "Direct" and len(self.users) > 1:
			frappe.throw(_("You can add only 1 user"))

	def on_update(self):
		# publish to users who belong only.
		frappe.publish_realtime('chat:room:update', dict(
			type = self.type,
			name = self.name,
			room_name = self.room_name,
			messages  = frappe.get_all('Chat Message', filters = {'room': name},	
				fields = ['name', 'message_content'])
		), after_commit = True)

	def on_trash(self):
		frappe.throw(_("Called!"))

@frappe.whitelist()
def create(kind, name = '', users = [ ]):
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
		resp = dict(
			type = resp.type, users = resp.users,
			name = resp.name, room_name = resp.room_name, 
			messages = frappe.get_all('Chat Message', filters = { 'room': name},
				fields = ['name', 'message_content'])
		)

	return resp