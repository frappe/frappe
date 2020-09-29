from __future__ import unicode_literals

# imports - module imports
from frappe.model.document import Document
from frappe import _
import frappe

# imports - frappe module imports
from frappe.chat import authenticate
from frappe.core.doctype.version.version import get_diff
from frappe.chat.doctype.chat_message import chat_message
from frappe.chat.util import (
	safe_json_loads,
	dictify,
	listify,
	squashify,
	get_if_empty
)

session = frappe.session


def is_direct(owner, other, bidirectional=False):
	def get_room(owner, other):
		room = frappe.get_all('Chat Room', filters=[
			['Chat Room', 'type', 'in', ('Direct', 'Visitor')],
			['Chat Room', 'owner', '=', owner],
			['Chat Room User', 'user', '=', other]
		], distinct=True)

		return room

	exists = len(get_room(owner, other)) == 1
	if bidirectional:
		exists = exists or len(get_room(other, owner)) == 1

	return exists


def get_chat_room_user_set(users, filter_=None):
	seen, uset = set(), list()

	for u in users:
		if filter_(u) and u.user not in seen:
			uset.append(u)
			seen.add(u.user)

	return uset


class ChatRoom(Document):
	def validate(self):
		if self.is_new():
			users = get_chat_room_user_set(self.users, filter_=lambda u: u.user != session.user)
			self.update(dict(
				users=users
			))

		if self.type == "Direct":
			if len(self.users) != 1:
				frappe.throw(_('{0} room must have atmost one user.').format(self.type))

			other = squashify(self.users)

			if self.is_new():
				if is_direct(self.owner, other.user, bidirectional=True):
					frappe.throw(_('Direct room with {0} already exists.').format(other.user))

		if self.type == "Group" and not self.room_name:
			frappe.throw(_('Group name cannot be empty.'))

	def on_update(self):
		if not self.is_new():
			before = self.get_doc_before_save()
			if not before: return

			after = self
			diff = dictify(get_diff(before, after))
			if diff:
				update = {}
				for changed in diff.changed:
					field, old, new = changed

					if field == 'last_message':
						new = chat_message.get(new)

					update.update({field: new})

				if diff.added or diff.removed:
					update.update(dict(users=[u.user for u in self.users]))

				update = dict(room=self.name, data=update)

				frappe.publish_realtime('frappe.chat.room:update', update, room=self.name,
						after_commit=True)


@frappe.whitelist(allow_guest=True)
def get(user=None, token=None, rooms=None, fields=None, filters=None):
	# There is this horrible bug out here.
	# Looks like if frappe.call sends optional arguments (not in right order),
	# the argument turns to an empty string.
	# I'm not even going to think searching for it.
	# Hence, the hack was get_if_empty (previous assign_if_none)
	# - Achilles Rasquinha achilles@frappe.io
	data = user or token
	authenticate(data)

	rooms, fields, filters = safe_json_loads(rooms, fields, filters)

	rooms = listify(get_if_empty(rooms, []))
	fields = listify(get_if_empty(fields, []))

	const = []  # constraints
	if rooms:
		const.append(['Chat Room', 'name', 'in', rooms])
	if filters:
		if isinstance(filters[0], list):
			const = const + filters
		else:
			const.append(filters)

	default = ['name', 'type', 'room_name', 'creation', 'owner', 'avatar']
	handle = ['users', 'last_message']

	param = [f for f in fields if f not in handle]

	rooms = frappe.get_all('Chat Room',
			or_filters=[
				['Chat Room', 'owner', '=', frappe.session.user],
				['Chat Room User', 'user', '=', frappe.session.user]
			],
			filters=const,
			fields=param + ['name'] if param else default,
			distinct=True
		)

	if not fields or 'users' in fields:
		for i, r in enumerate(rooms):
			droom = frappe.get_doc('Chat Room', r.name)
			rooms[i]['users'] = []

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


@frappe.whitelist(allow_guest=True)
def create(kind, token, users=None, name=None):
	authenticate(token)

	users = safe_json_loads(users)
	create = True

	if kind == 'Visitor':
		room = squashify(frappe.db.sql("""
			SELECT name
			FROM   `tabChat Room`
			WHERE  owner=%s
			""", (frappe.session.user), as_dict=True))

		if room:
			room = frappe.get_doc('Chat Room', room.name)
			create = False

	if create:
		room = frappe.new_doc('Chat Room')
		room.type = kind
		room.owner = frappe.session.user
		room.room_name = name

	dusers = []

	if kind != 'Visitor':
		if users:
			users = listify(users)
			for user in users:
				duser = frappe.new_doc('Chat Room User')
				duser.user = user
				dusers.append(duser)

			room.users = dusers
	else:
		dsettings = frappe.get_single('Website Settings')
		room.room_name = dsettings.chat_room_name

		users = [user for user in room.users] if hasattr(room, 'users') else []

		for user in dsettings.chat_operators:
			if user.user not in users:
				# appending user to room.users will remove the user from chat_operators
				# this is undesirable, create a new Chat Room User instead
				chat_room_user = {"doctype": "Chat Room User", "user": user.user}
				room.append('users', chat_room_user)

	room.save(ignore_permissions=True)

	room = get(token=token, rooms=room.name)
	if room:
		users = [room.owner] + [u for u in room.users]

		for user in users:
			frappe.publish_realtime('frappe.chat.room:create', room, user=user, after_commit=True)

	return room


@frappe.whitelist(allow_guest=True)
def history(room, user, fields=None, limit=10, start=None, end=None):
	if frappe.get_doc('Chat Room', room).type != 'Visitor':
		authenticate(user)

	fields = safe_json_loads(fields)

	mess = chat_message.history(room, limit=limit, start=start, end=end)
	mess = squashify(mess)

	return dictify(mess)
