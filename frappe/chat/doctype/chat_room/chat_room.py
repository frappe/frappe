# imports - standard imports
import json

# imports - module imports
import frappe
from   frappe.model.document import Document
from   frappe import _, _dict

# imports - frappe module imports
from   frappe.core.doctype.version.version import get_diff
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
            if is_one_on_one(self.owner, other.user, bidirectional = True):
                frappe.throw(_('Direct room with {other} already exists.'.format(
                    other = other.user
                )))

        if self.type == "Group" and not self.room_name:
            frappe.throw(_('Group name cannot be empty.'))
    
    # trigger from DocType
    def before_save(self):
        self.get_doc_before_save()

    def on_update(self):
        user   = session.user
        if self.owner != user:
            frappe.throw(_("Sorry! You don't enough permissions to update this room."))

        before = self.get_doc_before_save()
        after  = self

        # TODO
        # [ ] Check if DocType is itself updated. WARN if not.
        diff   = _dictify(get_diff(before, after)) # whoever you are, thank you for this.
        if diff:
            # notify only if there is an update.
            update = dict(name = self.name) # Update Goodies.
            # Types of Differences
            # 1. Changes
            for changed in diff.changed:
                field, old, new = changed

                update.update({
                    field: new
                })
            # 2. Added or Removed
            # TODO
            # [ ] Handle users.

            frappe.publish_realtime('frappe.chat:room:update', update,
                room = self.name, after_commit = True)

def is_one_on_one(owner, other, bidirectional = True):
    '''
    checks if the owner and other have a direct conversation room.
    '''
    def get_room(owner, other):
        room = frappe.get_list('Chat Room', filters = [
            ['Chat Room', 	   'type' , 'in', ('Direct', 'Visitor')],
            ['Chat Room', 	   'owner', '=' , owner],
            ['Chat Room User', 'user' , '=' , other]
        ], distinct = True)

        return room

    one_on_one = len(get_room(owner, other)) == 1
    if one_on_one and bidirectional:
        one_on_one = one_on_one and len(get_room(other, owner)) == 1
        
    return one_on_one

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
def create(kind, owner = None, users = None, name = None):
    if owner != session.user:
        frappe.throw(_("Sorry! You're not authorized to create a Chat Room."))

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
