from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _


class Constant(object):
    doctype_dict = {'todo': 'ToDo',
                    'help': 'Help',
                    'issue': 'Issue'}
    pass
