# imports - module imports
from   frappe.model.document import Document
from   frappe import _, _dict # <- the best thing ever happened to frappe
import frappe

# imports - frappe module imports
from   frappe.core.doctype.version.version import get_diff
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
    # trigger from DocType
    def before_save(self):
        if not self.is_new():
            self.get_doc_before_save()

    def on_update(self):
        user = get_user_doc()

        if user.chat_profile:
            if user.chat_profile != self.name:
                frappe.throw(_("Sorry! You don't have permission to update this profile."))
            else:
                if not self.is_new():
                    before = self.get_doc_before_save()
                    after  = self

                    diff   = dictify(get_diff(before, after))
                    if diff:
                        fields = [change[0] for change in diff.changed]

                        # NOTE: Version DocType is the best thing ever. Selective Updates to Chat Rooms/Users FTW.

                        # status update are dispatched to current user and Direct Chat Rooms.
                        if 'status' in fields:
                            # TODO: you can add filters within get_user_chat_rooms
                            rooms = get_user_chat_rooms(user)
                            rooms = [r for r in rooms if r.type == 'Direct']
                            resp  = dict(
                                user = user.name,
                                data = dict(
                                    status = self.status
                                )
                            )

                            for room in rooms:
                                frappe.publish_realtime('frappe.chat.profile:update', resp, room = room.name, after_commit = True)

                        if 'display_widget' in fields:
                            resp  = dict(
                                user = user.name,
                                data = dict(
                                    display_widget = bool(self.display_widget)
                                )
                            )
                            frappe.publish_realtime('frappe.chat.profile:update', resp, user = user.name, after_commit = True)

def get_user_chat_profile_doc(user = None):
    user = get_user_doc(user)
    prof = frappe.get_doc('Chat Profile', user.chat_profile)

    return prof

def get_user_chat_profile(user = None, fields = None):
    '''
    Returns the Chat Profile for a given user.
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
        chat_bg    = prof.chat_background,
        
        conversation_tones  = bool(prof.conversation_tones), # frappe, y u no jsonify 0,1 bools? :(
        display_widget      = bool(prof.display_widget)
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
    '''
    Creates a Chat Profile for the current session user, throws error if exists.
    '''
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

    prof  = get_user_chat_profile_doc(user)
    prof.update(data)
    prof.save()