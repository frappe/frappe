# imports - standard imports
import json

# imports - module imports
from   frappe.model.document import Document
from   frappe import _
import frappe

# imports - frappe module imports
from frappe.core.doctype.version.version import get_diff
from frappe.chat.doctype.chat_message	import chat_message
from frappe.chat.util import (
	get_user_doc,
	safe_json_loads,
	dictify,
	listify,
	squashify,
	assign_if_empty
)

session = frappe.session

# TODO
# [x] Only Owners can edit the DocType Record.
# [ ] Show Chat Room List that only has session.user in it.
# [ ] Make Chat Room pagination configurable.

class ChatRoom(Document):
	def validate(self):
		# TODO - Validations
		# [x] Direct/Visitor must have 2 users only.
		# [x] Groups must have 1 (1 being ther session user) or more users.
		# [x] Ensure group has a name.
		# [x] Check if there is a one-to-one conversation between 2 users (if Direct/Visitor).

		# First, check if user isn't stupid by adding many users or himself/herself.
		# C'mon yo, you're the owner.
		users = get_chat_room_user_set(self.users)
		users = [u for u in users if u.user != session.user]

		self.update(dict(
			users = users
		))

		if self.type in ("Direct", "Visitor"):
			if len(users) != 1:
				frappe.throw(_('{type} room must have atmost one user.'.format(
					type = self.type
				)))
			
			# squash to a single object if it's a list.
			other = squashify(users)

			# I don't know which idiot would make username not unique.
			# Remember, this entire app assumes validation based on user's email.

			# Okay, this must go only during creation. But alas, on click "Save" it does the same.
			if self.is_new():
				if is_one_on_one(self.owner, other.user, bidirectional = True):
					frappe.throw(_('Direct room with {other} already exists.'.format(
						other = other.user
					)))

		if self.type == "Group" and not self.room_name:
			frappe.throw(_('Group name cannot be empty.'))
	
	# trigger from DocType
	def before_save(self):
		if not self.is_new():
			self.get_doc_before_save()

	def on_update(self):
		user = session.user
		if user != self.owner:
			frappe.throw(_("Sorry! You don't enough permissions to update this room."))

		if not self.is_new():
			before = self.get_doc_before_save()
			after  = self

			# TODO
			# [ ] Check if DocType is itself updated. WARN if not.
			diff   = dictify(get_diff(before, after)) # whoever you are, thank you for this.
			if diff:
				# notify only if there is an update.
				update = dict() # Update Goodies.
				# Types of Differences
				# 1. Changes
				for changed in diff.changed:
					field, old, new = changed
					
					if field == 'last_message':
						doc_message = frappe.get_doc('Chat Message', new)
						update.update({
							field: dict(
								name     = doc_message.name,
								user     = doc_message.user,
								room     = doc_message.room,
								content  = doc_message.content,
								urls     = doc_message.urls,
								mentions = doc_message.mentions,
								creation = doc_message.creation
							)
						})
					else:
						update.update({
							field: new
						})
				# 2. Added or Removed
				# TODO
				# [ ] Handle users.
				# I personally feel this could be done better by either creating a new event
				# or attaching to the below event. Questions like Who removed Whom? Who added Whom? etc.
				# For first-cut, let's simply update the latest user list.
				# This is because the Version DocType already handles it.
				
				if diff.added or diff.removed:
					update.update({
						'users': [u.user for u in self.users]
					})

				resp   = dict(
					room = self.name,
					data = update
				)

				frappe.publish_realtime('frappe.chat.room:update', resp,
					room = self.name, after_commit = True)

	# def on_trash(self):
	# 	if self.owner != session.user:
	# 		frappe.throw(_("Sorry, you're not authorized to delete this room."))

def is_admin(user, room):
	if user != session.user:
		frappe.throw(_("Sorry, you're not authorized to view this information."))

	# TODO - I'm tired searching the bug.

def is_one_on_one(owner, other, bidirectional = False):
	'''
	checks if the owner and other have a direct conversation room.
	'''
	def get_room(owner, other):
		room = frappe.get_all('Chat Room', filters = [
			['Chat Room', 	   'type' , 'in', ('Direct', 'Visitor')],
			['Chat Room', 	   'owner', '=' , owner],
			['Chat Room User', 'user' , '=' , other]
		], distinct = True)

		return room

	exists = len(get_room(owner, other)) == 1
	if bidirectional:
		exists = exists or len(get_room(other, owner)) == 1
	
	return exists

def get_chat_room_user_set(users):
	'''
	Returns a set of Chat Room Users

	:param users: sequence of Chat Room Users
	:return: set of Chat Room Users
	'''
	seen, news = set(), list()

	for u in users:
		if u.user not in seen:
			news.append(u)
			seen.add(u.user)

	return news





# Could we move pagination to a config, but how?
# One possibility is to add to Chat Profile itself.
# Actually yes.
@frappe.whitelist()
def get_history(room, user = None, pagination = 20):
	user = get_user_doc(user)
	mess = chat_message.get_messages(room, pagination = pagination)

	mess = squashify(mess)
	
	return dictify(mess)

def authenticate(user):
	if user != session.user:
		frappe.throw(_("Sorry, you're not authorized."))

@frappe.whitelist()
def get(user, rooms = None, fields = None, filters = None):
	# There is this horrible bug out here.
	# Looks like if frappe.call sends optional arguments (not in right order), the argument turns to an empty string.
	# I'm not even going to think searching for it.
	# Hence, the hack was assign_if_empty (previous assign_if_none)
	# - Achilles Rasquinha achilles@frappe.io

	authenticate(user)

	rooms, fields, filters = safe_json_loads(rooms, fields, filters)

	rooms   = listify(assign_if_empty(rooms,  [ ]))
	fields  = listify(assign_if_empty(fields, [ ]))

	const   = [ ] # constraints
	if rooms:
		const.append(['Chat Room', 'name', 'in', rooms])
	if filters:
		if isinstance(filters[0], list):
			const = const + filters
		else:
			const.append(filters)

	default = ['name', 'type', 'room_name', 'creation', 'owner', 'avatar']
	handle  = ['users', 'last_message']
	
	param   = [f for f in fields if f not in handle]

	rooms   = frappe.get_all('Chat Room',
		or_filters = [
			['Chat Room', 'owner', '=', user],
			['Chat Room User', 'user', '=', user]
		],
		filters    = filters,
		fields     = param + ['name'] if param else default,
		distinct   = True,
		debug      = True
	)

	if not fields or 'users' in fields:
		for i, r in enumerate(rooms):
			droom = frappe.get_doc('Chat Room', r.name)
			rooms[i]['users'] = [ ]

			for duser in droom.users:
				rooms[i]['users'].append(duser.user)

	if not fields or 'last_message' in fields:
		for i, r in enumerate(rooms):
			droom = frappe.get_doc('Chat Room', r.name)
			if droom.last_message:
				rooms[i]['last_message'] = chat_message.get(droom.last_message)
			else:
				rooms[i]['last_message'] = None

	rooms = squashify(dictify(rooms))
	
	return rooms

@frappe.whitelist()
def create(kind, owner, users = None, name = None):
	authenticate(owner)

	users = safe_json_loads(users)

	room  = frappe.new_doc('Chat Room')
	room.type  = kind
	room.owner = owner
	dusers     = [ ]

	if users:
		users  = listify(users)
		for user in users:
			duser 	   = frappe.new_doc('Chat Room User')
			duser.user = user
			dusers.append(duser)
	
	room.users = dusers
	room.save(ignore_permissions = True)

	room  = get(owner, rooms = room.name)
	users = [room.owner] + [u for u in room.users]

	for u in users:
		frappe.publish_realtime('frappe.chat.room:create', room, user = u, after_commit = True)

	return room