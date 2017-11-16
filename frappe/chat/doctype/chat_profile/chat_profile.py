# imports - standard imports
import json

# imports - module imports
from   frappe.model.document import Document
from   frappe import _, _dict # <- the best thing ever happened to frappe
import frappe

# imports - frappe module imports
from   frappe.chat.doctype.chat_room.chat_room import get_user_chat_room
from   frappe.chat.util import (
    get_user_doc
)

session = frappe.session

# TODOs
# User
# [ ] Deleting User should also delete its Chat Profile.
# [ ] Ensuring username is mandatory when User has been created.

# Chat Profile
# [x] Link Chat Profile DocType to User when User is created.
# [x] Once done, add a validator to check Chat Profile has been
#     created only once. Should be done on `validate`.
# [x] Users can view other Users Chat Profile, but not update the same.
#     Not sure, but circular link would be helpful.

class ChatProfile(Document):
    def on_update(self):
        user = get_user_doc()

        if user.chat_profile:
            if user.chat_profile != self.name:
                frappe.throw(_("Sorry! You don't have permission to update this profile."))

def get_user_chat_profile_doc(user = None):
    user = get_user_doc(user)
    prof = frappe.get_doc('Chat Profile', user.chat_profile)

    return prof

def get_user_chat_profile(user = None, fields = None):
    '''
    Returns the Chat Profile of a given user.
    '''
    user = get_user_doc(user)
    prof = get_user_chat_profile_doc(user)

    data = dict(
        name 	   = user.name, 
        username   = user.username,
        first_name = user.first_name, 
        last_name  = user.last_name,
        avatar 	   = user.user_image,
        bio        = user.bio,
        status	   = prof.status,
        chat_bg    = prof.chat_background
    )

    if fields:
        copy = dict()
        for field in fields:
            if field not in data:
                frappe.throw(_("No field {field} found in Chat Profile.".format(
                    field = field
                )))
            else:
                copy.update({
                    field: data[field]
                })
        data = copy

    return data

def get_new_chat_profile_doc(user = None):
    user = get_user_doc(user)

    prof = frappe.new_doc('Chat Profile')

    return prof

@frappe.whitelist()
def create(user, exist_ok = False, fields = None):
    exist  = json.loads(exist_ok)
    fields = json.loads(fields)

    user   = get_user_doc(user)

    if user.name != session.user:
        frappe.throw(_("Sorry! You don't have permission to create {user}'s profile.".format(
            user = user.name
        )))

    if user.chat_profile:
        if not exist_ok:
            frappe.throw(_("Sorry! You cannot create more than one Chat Profile."))
        
        prof = get_user_chat_profile(user, fields)
    else:
        prof = get_new_chat_profile_doc(user)
        prof.save()

        user.update(dict(
            chat_profile = prof.name
        ))
        user.save()

        prof = get_user_chat_profile(user, fields)

    return _dict(prof)

@frappe.whitelist()
def get(user = None, fields = None):
    '''
    Returns a user's Chat Profile.
    '''
    fields = json.loads(fields)
    prof   = get_user_chat_profile(user, fields)

    return _dict(prof)

@frappe.whitelist()
def update(user, data):
    data = json.loads(data)
    user = get_user_doc(user)

    if user.name != session.user:
        frappe.throw(_("Sorry! You don't have permission to update {user}'s profile.".format(
            user = user.name
        )))

    prof = get_user_chat_profile_doc(user.name)
    prof.update(data)
    prof.save()

    # only send that has been updated.
    prof = get_user_chat_profile(user.name, fields = data.keys())
    resp = dict(
        user = user.name,
        data = prof
    )

    room = get_user_chat_room(user) # one or more, okay?
    for r in room:
        if r.type in ('Direct', 'Vistor'):
            frappe.publish_realtime('frappe.chat:profile:update', resp,
                room = r.name)