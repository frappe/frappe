from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _


class Engine(object):

    def get_reply(self, obj):
        reply = None
        try:
            className = doctype_dict.get(doctype, 'Error') + 'Bot'
            reply = globals()[className](
                doctype, query, action, id).get_results()
        except Exception, exce:
            msg = 'Oops, you are not allowed to know that'
            message = format_message(msg, [], 'nothing')
            info = format_info('', False, False, False, [])
            reply = format_output(doctype, message, info)
        return reply
