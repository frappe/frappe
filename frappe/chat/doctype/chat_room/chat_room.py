# imports - standard imports
import json

# imports - module imports
import frappe
from   frappe.model.document import Document
from   frappe import _, _dict

# imports - frappe module imports
from   frappe.chat.doctype.chat_message.chat_message import get_messages
from   frappe.chat.util import (
    get_user_doc,
    safe_json_loads,
    _dictify,
    squashify
)

session = frappe.session

# TODO
# [x] Only Owners can edit the DocType Record.
# [ ] Show Chat Room List that only has session.user in it.
# [ ] Make Chat Room pagination configurable.

class ChatRoom(Document):
    def validate(self):
        # TODO - Validation Kinds
        # [x] Direct must have 2 users only.
        # [x] Groups must have 1 or more users.
        # [x] Ensure group name exists.
        # [x] Check if the direct group between 2 users exists.
        # [ ] Don't display # ChatRoom-Issue-1

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
            
            # Check if room exists between these two users.
            other = squashify(users)
            # I could add another parameter called "bidirectional = True" but man, who gives a damn?
            # ChatRoom-Issue-1
            # Okay, this must go only during creation. But alas, on click "Save" it does the same.
            if is_one_on_one(self.owner, other.user) or is_one_on_one(other.user, self.owner):
                frappe.throw(_('Direct room with {other} already exists.'.format(
                    other = other.user
                )))

        if self.type == "Group" and not self.room_name:
            frappe.throw(_('Group name cannot be empty.'))

    def on_update(self):
        user = session.user
        if self.owner != user:
            frappe.throw(_("Sorry! You don't have permission to update this room."))

def is_one_on_one(owner, other):
    '''
    checks if the owner and other have a direct conversation room.
    '''
    room = frappe.get_list('Chat Room', filters = [
        ['Chat Room', 	   'type' , 'in', ('Direct', 'Visitor')],
        ['Chat Room', 	   'owner', '=' , owner],
        ['Chat Room User', 'user' , '=' , other]
    ], distinct = True)

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

@frappe.whitelist()
def get_user_chat_rooms(user = None, rooms = None, fields = None):
    # TODO
    # [ ] Query based on room name.
    '''
    if user is None, defaults to session user.
    if room is None, returns the entire list of rooms subscribed by user.
    '''
    user  = get_user_doc(user)
    rooms = frappe.get_list('Chat Room',
        or_filters = [
            ['Chat Room', 'owner', '=', user.name],
            ['Chat Room User', 'user', '=', user.name]
        ],
        fields     = fields if fields else [
            'type', 'name', 'owner', 'room_name', 'avatar'
        ],
        distinct   = True
    )

    # get information from child table.
    for i, r in enumerate(rooms):
        doc_room		  = frappe.get_doc('Chat Room', r.name)
        rooms[i]['users'] = [ ]

        for user in doc_room.users:
            rooms[i]['users'].append(user.user)

    return rooms

@frappe.whitelist()
def create(kind, owner = None, name = None, users = None):
    room = get_new_chat_room(kind, owner, name, users)

@frappe.whitelist()
def get(user, room = None, fields = None):
    room   = safe_json_loads(room)
    fields = safe_json_loads(fields)

    user   = get_user_doc(user)

    if user.name != frappe.session.user:
        frappe.throw(_("You're not authorized to view this room."))

    data = get_user_chat_rooms(user, room)
    resp = squashify(data) # <- you're welcome - achilles@frappe.io
    
    return _dictify(resp)

# Could we move pagination to a config, but how?
# One possibility is to add to Chat Profile itself.
# Actually yes.
@frappe.whitelist()
def get_history(room, user = None, pagination = 20):
    user = get_user_doc(user)
    mess = get_messages(room, pagination = 20)

    mess = squashify(mess)

    return _dictify(mess)
