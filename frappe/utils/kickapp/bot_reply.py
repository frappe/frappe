from __future__ import unicode_literals

import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
import json
from frappe.async import get_redis_server
from frappe import conf
from frappe.utils.kickapp.bot_decision import Decision
from frappe.utils.kickapp.bot_helper import format_output, format_message, format_info

doctype_dict = {'todo': 'ToDo', 'help': 'Help', 'issue': 'Issue'}
action_dict = frappe._dict({'Create': 'create',
                            'Update': 'update',
                            'Delete': 'delete',
                            'More': 'more',
                            'Nothing': 'nothing'})


@frappe.whitelist()
def get_reply(data):
    print data
    # msg = ReplyHelper().get_reply(data.doctype, data.text, data.action, data)
    # frappe.publish_realtime('message_from_server', msg,
    #                         room='{1}{2}{3}'.format('192.168.0.106', ':', data.room))


class Bot(Decision):

    def __init__(self, doctype, query, action, _id):
        Decision.__init__(self, doctype, query, action)
        self._id = _id


class ErrorBot(Bot):

    def __init__(self, doctype, query, action, _id):
        Bot.__init__(self, doctype, query, action, _id)

    def get_results(self):
        msg = 'Didn\'t get that, try something like \'Create new todo\'.'
        message = format_message(msg, [], 'nothing')
        info = format_info('', False, False, False, [])
        return format_output(self.doctype, message, info)


class ToDoBot(Bot):

    def __init__(self, doctype, query, action, _id):
        Bot.__init__(self, doctype, query, action, _id)
        self.func_list = ['create', 'update', 'delete', 'get']
        self.fields = ["name", "description", "priority", "creation", "status"]

    def get_results(self):
        '''self.push_prev_client(self.query)'''

        try:
            if self.action == action_dict.Nothing:
                for func_name in self.func_list:
                    list_of_keywords = self.generate(self.doctype, func_name)
                    if self.has(list_of_keywords):
                        return getattr(self, func_name)(0)
            elif self.action == action_dict.Create:
                return getattr(self, 'create')(1)

            elif self.action == action_dict.More:
                if self.query == 'delete':
                    return getattr(self, 'delete')(self._id)
                elif self.query == 'get':
                    return getattr(self, 'get')(self._id)
                elif self.query == 'update':
                    return getattr(self, 'update')(self._id)

            elif ((self.action == action_dict.Update or self.action == action_dict.Delete) and self._id != -1):
                if self.action == action_dict.Delete:
                    return getattr(self, 'delete')(1)
                elif self.action == action_dict.Update:
                    return getattr(self, 'update')(1)

        except Exception, exce:
            return self.prepare_message('Something went wrong, Try again in a little bit.',
                                        [], action_dict.Nothing, '', False, False, False, [], self.doctype)

        return self.prepare_message('Didn\'t get that, try something like \'Create new todo\'.',
                                    [], action_dict.Nothing, '', False, False, False, [], self.doctype)

    def prepare_message(self, msg, _list, action, button_text,
                        is_interactive, is_interactive_chat,
                        is_interactive_list, fields, doctype):
        message = format_message(msg, _list, action)
        info = format_info(button_text, is_interactive,
                           is_interactive_chat, is_interactive_list, fields)
        return format_output(doctype, message, info)

    def create(self, e):
        if e == 1:
            todo_doc = frappe.new_doc(doctype_dict[self.doctype])
            todo_doc.description = self.query
            todo_doc.save()
            frappe.db.commit()
            _list = frappe.get_list(doctype_dict[self.doctype], fields=self.fields, filters={
                                    "name": todo_doc.name})
            return self.prepare_message('A new Todo has been created.',
                                        _list, action_dict.Nothing, 'View Info', True, True, False, self.fields, self.doctype)

        elif e == 0:
            return self.prepare_message('Alright, Please enter description of new Todo.',
                                        [], action_dict.Create, '', False, False, False, [], self.doctype)

    def delete(self, e):
        if e == 1:
            frappe.delete_doc(doctype_dict[self.doctype], self._id)
            frappe.db.commit()
            return self.prepare_message('Todo has been deleted.',
                                        [], action_dict.Nothing, '', False, False, False, [], self.doctype)

        elif e == 0:
            _list = frappe.get_list(doctype_dict[
                                    self.doctype], fields=self.fields, limit_start=1, limit_page_length=3)
            return self.prepare_message('Alright, Please select the todo you want to delete.',
                                        _list, action_dict.Delete, 'View More', True, False, True, self.fields, self.doctype)
        elif e > 200:
            page = e - 200
            _list = frappe.get_list(
                doctype_dict[self.doctype], fields=self.fields, limit_start=page)
            return self.prepare_message('Here is list of todo\'s.',
                                        _list, action_dict.Delete, 'View More', True, False, True, self.fields, self.doctype)

    def update(self, e):
        if e == 1:
            frappe.set_value(
                doctype_dict[self.doctype], self._id, "description", self.query.capitalize())
            frappe.db.commit()
            _list = frappe.get_list(
                doctype_dict[self.doctype], fields=self.fields, filters={"name": self._id})
            return self.prepare_message('Todo has been updated.',
                                        _list, action_dict.Nothing, 'View Info', True, True, False, self.fields, self.doctype)

        elif e == 0:
            _list = frappe.get_list(doctype_dict[
                                    self.doctype], fields=self.fields, limit_start=1, limit_page_length=3)
            return self.prepare_message('Alright, Please select the todo you want to update.',
                                        _list, action_dict.Update, 'View More', True, False, True, self.fields, self.doctype)
        elif e > 200:
            page = e - 200
            _list = frappe.get_list(
                doctype_dict[self.doctype], fields=self.fields, limit_start=page)
            return self.prepare_message('Here is list of todo\'s.',
                                        _list, action_dict.Update, 'View More', True, False, True, self.fields, self.doctype)

    def get(self, e):
        if e == 0 or e == 1:
            _list = frappe.get_list(doctype_dict[
                                    self.doctype], fields=self.fields, limit_start=1, limit_page_length=3)
            return self.prepare_message('Here is list of todo\'s.',
                                        _list, action_dict.Nothing, 'View More', True, False, True, self.fields, self.doctype)

        elif e > 200:
            page = e - 200
            _list = frappe.get_list(
                doctype_dict[self.doctype], fields=self.fields, limit_start=page)
            return self.prepare_message('Here is list of todo\'s.',
                                        _list, action_dict.Nothing, 'View More', True, False, True, self.fields, self.doctype)


class ReplyHelper(object):

    def get_reply(self, doctype, query, action, id):
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
