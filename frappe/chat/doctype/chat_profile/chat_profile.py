# imports - module imports
from   frappe.model.document import Document
from   frappe import _, _dict # <- the best thing ever happened to frappe
import frappe

# imports - frappe module imports
from   frappe.chat.doctype.chat_room.chat_room import get_user_chat_rooms
from   frappe.chat.util import (
    get_user_doc,
    safe_json_loads,
    filter_dict,
    dictify
)

session = frappe.session

# TODO
# User
# [ ] Deleting a User should also delete its Chat Profile.
# [ ] Ensuring username is mandatory when User has been created.

# Chat Profile
# [x] Link Chat Profile DocType to User when User has been created.
# [x] Once done, add a validator to check Chat Profile has been
#     created only once.
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
        email      = user.email,
        first_name = user.first_name,
        last_name  = user.last_name,
        username   = user.username,
        avatar 	   = user.user_image,
        bio        = user.bio,

        status	   = prof.status,
        chat_bg    = prof.chat_background
    )

    try:
        data = filter_dict(data, fields)
    except KeyError as e:
        frappe.throw(str(e))

    return data

def get_new_chat_profile_doc(user = None, link = True):
    user = get_user_doc(user)
    prof = frappe.new_doc('Chat Profile')
    prof.save()

    if link:
        user.update(dict(
            chat_profile = prof.name
        ))
        user.save()

    return prof

@frappe.whitelist()
def create(user, exists_ok = False, fields = None):
    exists, fields = safe_json_loads(exists_ok, fields)
    user           = get_user_doc(user)

    if user.name  != session.user:
        frappe.throw(_("Sorry! You don't have permission to create a profile for user {name}.".format(
            name   = user.name
        )))

    if user.chat_profile:
        if not exists:
            frappe.throw(_("Sorry! You cannot create more than one Chat Profile."))
        
        prof = get_user_chat_profile(user, fields)
    else:
        prof = get_new_chat_profile_doc(user)
        prof = get_user_chat_profile(user, fields)

    return dictify(prof)

@frappe.whitelist()
def get(user = None, fields = None):
    '''
    Returns a user's Chat Profile.
    '''
    fields = safe_json_loads(fields)
    prof   = get_user_chat_profile(user, fields)

    return dictify(prof)

@frappe.whitelist()
def update(user, data):
    data  = safe_json_loads(data)
    user  = get_user_doc(user)

    if user.name != session.user:
        frappe.throw(_("Sorry! You don't have permission to update Chat Profile for user {name}.".format(
            name  = user.name
        )))

    prof  = get_user_chat_profile_doc(user.name)
    prof.update(data)
    prof.save()

    # only send that has been updated.
    prof  = get_user_chat_profile(user, fields = data.keys())
    resp  = dict(
        user = user.name,
        data = prof
    )

    if 'status' in data:
        rooms = get_user_chat_rooms(user) # one or more, okay?
        rooms = [r for r in rooms if r.type in ('Direct', 'Visitor')]
        for room in rooms:
            frappe.publish_realtime('frappe.chat.profile.update', resp, room = room.name, after_commit = True)