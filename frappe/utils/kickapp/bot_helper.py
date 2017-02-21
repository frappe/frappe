
from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
from frappe import conf


def format_output(doctype, message, info):
    return {'doctype': doctype, 'message': message, 'info': info}

def format_message(message, _list, action):
    return{'message':message, 'list':_list, 'action':action}

def format_info(button_text, is_interactive, is_interactive_chat, is_interactive_list, fields):
    return {'button_text':button_text, 'is_interactive':is_interactive, 'is_interactive_chat':is_interactive_chat, 'is_interactive_list':is_interactive_list, 'fields':fields}

class Helpers(object):
    ''' Create all possible message by an user to create new data '''

    def create_keywords(self, doctype):
        return ['create', '{0} {1}'.format('create new', doctype), '{0} {1}'.format('create a', doctype),
                '{0} {1}'.format('create my', doctype),
                '{0} {1}'.format('create', doctype),
                '{0} {1}'.format('hey create new', doctype),
                '{0} {1}'.format('hey create', doctype),
                '{0} {1}'.format('make new', doctype),
                '{0} {1}'.format('make a', doctype),
                '{0} {1}'.format('make', doctype)]

    ''' Create all possible message by an user to update new data '''

    def update_keywords(self, doctype):
        return ['update', '{0} {1}'.format('update', doctype),
                '{0} {1}'.format('update a', doctype),
                '{0} {1}'.format('update my', doctype)]

    ''' Create all possible message by an user to delete new data '''

    def delete_keywords(self, doctype):
        return ['delete', '{0} {1}'.format('delete', doctype),
                '{0} {1}'.format('delete a', doctype),
                '{0} {1}'.format('delete my', doctype)]

    ''' Create all possible message by an user to create new data '''

    def get_keywords(self, doctype):
        return ['get', 'list', '{0} {1}'.format('list', doctype), '{0} {1}'.format('get', doctype),
                '{0} {1}'.format('get all', doctype),
                '{0} {1}'.format('get my', doctype),
                '{0} {1} {2}'.format('get', doctype, 's'),
                '{0} {1} {2}'.format('get all', doctype, 's'),
                '{0} {1} {2}'.format('get my', doctype, 's')]
