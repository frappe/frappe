# imports - module imports
import frappe
from   frappe.model.document import Document
from   frappe import _, _dict

# imports - frappe module imports
from   frappe.chat.util import (
	get_user_doc,
	safe_literal_eval,
	_dictify,
	squashify
)

session = frappe.session

# TODOs
# [ ] Only Owners can edit the DocType Record.
# [ ] Show Chat Room List that only has session.user in it.

class ChatRoom(Document):
	def validate(self):
		# Validation Kinds
		# [x] Direct must have 2 users only.
		# [x] Groups must have 1 or more users.
		# [x] Ensure group name exists.
		# [ ] Check if the direct group between 2 users exists.

		# First, check if user isn't stupid by adding many users or himself/herself.
		# C'mon yo, you're the owner.
		users = get_chat_room_user_set(self.users)
		users = [u for u in users if u.user != session.user]

		self.update(dict(
			users = users
		))

		if self.type in ("Direct", "Visitor"):
			if len(users) != 1:
				frappe.throw(_('Direct room must have atmost one user.'))
			
			# Check if room exists between these two users.
			other = squashify(users)
			if direct_room_exist(self.owner, other.user) or direct_room_exist(other.user, self.owner):
				frappe.throw(_('Direct room with {other} already exists.'.format(
					other = other.user
				)))

		if self.type == "Group" and not self.room_name:
			frappe.throw(_('Group name cannot be empty.'))

	def on_update(self):
		user = session.user
		if self.owner != user:
			frappe.throw(_("Sorry! You don't have permission to update this room."))

def direct_room_exist(owner, other):
	room = frappe.get_list('Chat Room', filters = [
		['Chat Room', 	   'type' , 'in', ('Direct', 'Visitor')],
		['Chat Room', 	   'owner', '=' , owner],
		['Chat Room User', 'user' , '=' , other]
	])

	return len(room) == 1

def get_chat_room_user_set(users):
	seen  = set()
	news  = [ ]

	for u in users:
		if u.user not in seen:
			news.append(u)

			seen.add(u.user)

	return news

def get_new_chat_room_doc(kind, owner = None, name = None, users = None):
	room = frappe.new_doc('Chat Room')
	room.type  	   = kind
	room.owner 	   = owner
	room.room_name = name
	
	return room

def get_new_chat_room(kind, owner = None, name = None, users = None):
	room = get_new_chat_room_doc(kind, owner, name, users)
	room.save()

def get_user_chat_room(user = None, room = None, fields = None):
	# TODO
	# [ ] Handle fields.
	# [ ] Query based on roon names.
	'''
	if user is None, defaults to session user.
	if room is None, returns the entire list of rooms subscribed by user.
	'''
	user = get_user_doc(user)
	room = frappe.get_list('Chat Room',
		or_filters = [
			['Chat Room', 'owner', '=', user],
			['Chat Room User', 'user', '=', user]
		],
		fields     = ['type', 'name', 'owner', 'room_name', 'avatar'],
		distinct   = True
	)
	for i, r in enumerate(room):
		room[i]['users'] = [ ]
		rdoc			 = frappe.get_doc('Chat Room', r.name)

		for user in rdoc.users:
			room[i]['users'].append(user.user)

	return squashify(room)

def get_all_user_rooms(user, fields=None):
	if not fields:
		fields = ['type', 'name', 'owner', 'room_name', 'avatar']
	return frappe.get_list('Chat Room',
		or_filters = [
			['Chat Room', 'owner', '=', user],
			['Chat Room User', 'user', '=', user]
		],
		fields     = fields,
		distinct   = True
	)

def get_rooms():
	'''get rooms for the current user. called from hooks'''
	return [d.name for d in get_all_user_rooms(frappe.session.user, fields = ['name'])]

@frappe.whitelist()
def create(kind, owner = None, name = None, users = None):
	room = get_new_chat_room(kind, owner, name, users)

@frappe.whitelist()
def get(user, room = None, fields = None):
	room, fields = safe_literal_eval(room, fields)
	user   		 = get_user_doc(user)

	if user.name != frappe.session.user:
		frappe.throw(_("You're not authorized to view this room."))

	data = get_user_chat_room(user, room)
	resp = _dictify(data) # <- you're welcome - achilles@frappe.io
	
	return resp

@frappe.whitelist()
def get_history(room):
	pass