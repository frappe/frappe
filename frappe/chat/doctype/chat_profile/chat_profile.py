from __future__ import unicode_literals

# imports - module imports
from   frappe.model.document import Document
from   frappe import _
import frappe

# imports - frappe module imports
from   frappe.core.doctype.version.version import get_diff
from   frappe.chat.doctype.chat_room       import chat_room
from   frappe.chat.util import (
    safe_json_loads,
    filter_dict,
    dictify
)

session = frappe.session

class ChatProfile(Document):
    def before_save(self):
        if not self.is_new():
            self.get_doc_before_save()

    def on_update(self):
        if not self.is_new():
            b, a = self.get_doc_before_save(), self
            diff = dictify(get_diff(a, b))
            if diff:
                user   = session.user

                fields = [changed[0] for changed in diff.changed]

                if 'status' in fields:
                    rooms  = chat_room.get(user, filters = ['Chat Room', 'type', '=', 'Direct'])
                    update = dict(user = user, data = dict(status = self.status))

                    for room in rooms:
                        frappe.publish_realtime('frappe.chat.profile:update', update, room = room.name, after_commit = True)

                if 'enable_chat' in fields:
                    update = dict(user = user, data = dict(enable_chat = bool(self.enable_chat)))
                    frappe.publish_realtime('frappe.chat.profile:update', update, user = user, after_commit = True)

def authenticate(user):
    if user != session.user:
        frappe.throw(_("Sorry, you're not authorized."))

@frappe.whitelist()
def get(user, fields = None):
    duser   = frappe.get_doc('User', user)
    dprof   = frappe.get_doc('Chat Profile', user)

    # If you're adding something here, make sure the client recieves it.
    profile = dict(
        # User
        name       = duser.name,
        email      = duser.email,
        first_name = duser.first_name,
        last_name  = duser.last_name,
        username   = duser.username,
        avatar     = duser.user_image,
        bio        = duser.bio,
        # Chat Profile
        status             = dprof.status,
        chat_background    = dprof.chat_background,
        message_preview    = bool(dprof.message_preview),
        notification_tones = bool(dprof.notification_tones),
        conversation_tones = bool(dprof.conversation_tones),
        enable_chat        = bool(dprof.enable_chat)
    )
    profile = filter_dict(profile, fields)

    return dictify(profile)

@frappe.whitelist()
def create(user, exists_ok = False, fields = None):
    authenticate(user)

    exists_ok, fields = safe_json_loads(exists_ok, fields)

    result = frappe.db.sql("""
        SELECT *
        FROM `tabChat Profile`
        WHERE `user` = '{user}'
    """.format(user = user))

    if result:
        if not exists_ok:
            frappe.throw(_('Chat Profile for User {0} exists.').format(user))
    else:
        dprof      = frappe.new_doc('Chat Profile')
        dprof.user = user
        dprof.save(ignore_permissions = True)

    profile = get(user, fields = fields)

    return profile

@frappe.whitelist()
def update(user, data):
    authenticate(user)

    data  = safe_json_loads(data)

    dprof = frappe.get_doc('Chat Profile', user)
    dprof.update(data)
    dprof.save(ignore_permissions = True)