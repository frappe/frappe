from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
from frappe.utils.kickapp.helper import get_doctype_from_bot_name, create_bot_message_object
import datetime


class Engine(object):

    def get_reply(self, obj):
        reply = {}
        class_name = None
        try:
            class_name = get_doctype_from_bot_name(obj.bot_name)
            reply = globals()[class_name](obj).get_results()
        except Exception, exce:
            msg_obj = frappe._dict({
                "bot_name": class_name,
                "text": "Something went wrong, Please try in a little bit.",
                "created_at": str(datetime.datetime.now())
            })
            reply = create_bot_message_object(obj.room, msg_obj, True)
        return reply
