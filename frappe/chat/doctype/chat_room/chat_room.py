# imports - module imports
import frappe
from   frappe.model.document import Document
from   frappe import _

session = frappe.session

# TODOs
# [ ] Validation for more than one 
# [ ] Ensure Group name exist

class ChatRoom(Document):
	def validate(self):
		# Validation Kinds
		# 1. Direct must have 2 users only.
		# 2. Groups must have 1 or more users.

		# First, check if user isn't stupid by adding many users or himself.
		# C'mon yo, you're the owner.
		users = doc.users
		

		if self.type in ("Direct", "Visitor") and len(self.users) > 1:
			frappe.throw(_('Direct room must have atmost one user only.'))

		

	def on_update(self):
		# publish to users who belong only.
		# frappe.publish_realtime('chat:room:update', dict(
		# 	type = self.type,
		# 	name = self.name,
		# 	room_name = self.room_name,
		# 	messages  = frappe.get_all('Chat Message', filters = {'room': name},	
		# 		fields = ['name', 'message_content'])
		# ), after_commit = True)
		pass

	def on_trash(self):
		pass

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