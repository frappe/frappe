from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
from frappe.utils.kickapp.helper import get_doctype_from_bot_name, create_bot_message_object


class Engine(object):

    def get_reply(self, room, query):
        reply = {}
        class_name = None
        try:
            class_name = get_doctype_from_bot_name(query.bot_name)
            reply = globals()[class_name](room, query).get_results()
        except Exception, exce:
            print exce
            msg_obj = {
                "bot_name": class_name,
                "text": "Something went wrong, Please try in a little bit."
            }
            reply = create_bot_message_object(room, msg_obj, True)
        return reply




