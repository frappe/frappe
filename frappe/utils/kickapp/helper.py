from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
import json
from frappe import conf
from frappe.utils.kickapp.constant import Constant


@frappe.whitelist()
def get_dev_port():
    return conf.get("developer_mode"), conf.get('socketio_port')


''' misc functions '''


def get_doctype_from_bot_name(bot_name):
    return Constant.doctype_dict.get(bot_name, 'Error')

''' functions related to message formating '''


def create_bot_message_object(room, chat, is_null):
    if is_null:
        return {
            "room": room,
            "is_bot": 'true',
            "bot_name": chat.bot_name,
            "created_on": get_date(chat.modified),
            "text": chat.text,
            "action": {},
            "info": {},
            "list_items": {}
        }
    else:
        return {
            "room": room,
            "is_bot": 'true',
            "bot_name": chat.bot_name,
            "created_on": get_date(chat.modified),
            "text": chat.text,
            "action": format_action_to_json(chat.action),
            "info": format_info_to_json(chat.info),
            "list_items": format_list_items_to_json(chat.list_items)
        }


def format_response(is_bot, chats, room):
    if is_bot == 'true':
        return format_response_for_bot(chats, room)
    else:
        return format_response_for_others(chats, room)


def format_response_for_bot(chats, room):
    results = []
    for chat in chats:
        item = {
            "room": room,
            "is_bot": 'true',
            "bot_name": chat.bot_name,
            "created_on": get_date(chat.modified),
            "text": chat.text,
            "action": format_action_to_json(chat.action),
            "info": format_info_to_json(chat.info),
            "list_items": format_list_items_to_json(chat.list_items)
        }
        results.append(item)
    return results


def format_response_for_others(chats, room):
    results = []
    for chat in chats:
        item = {
            "room": room,
            "is_bot": 'false',
            "created_on": get_date(chat.modified),
            "user_name": chat.user_name,
            "user_id": chat.user_id,
            "text": chat.text,
            "is_alert": chat.is_alert,
            "chat_title": chat.chat_title,
            "chat_type": chat.chat_type
        }
        results.append(item)
    return results


def format_list_items_to_json(list_items):
    return json.loads(list_items)


def format_info_to_json(info):
    return json.loads(info)


def format_action_to_json(action):
    return json.loads(action)


def get_date(modified):
    created_on = str(modified)
    return created_on.split('.')[0]


def format_list_items_before_adding_to_database(action_on_internal_item_click, list_items):
    return {
        "action_on_internal_item_click": action_on_internal_item_click,
        "items": get_items_from_array(list_items)
    }


def format_action_before_adding_to_database(action_on_button_click, action_on_list_item_click):
    return {
        "action_on_button_click": action_on_button_click,
        "action_on_list_item_click": action_on_list_item_click
    }


def format_info_before_adding_to_database(button_text, is_interactive_chat, is_interactive_list):
    return {
        "button_text": button_text,
        "is_interactive_chat": is_interactive_chat,
        "is_interactive_list": is_interactive_list
    }


def get_items_from_array(items):
    if items:
        results = []
        for item in items:
            keys = item.keys()
            results.append(get_object_fron_key_value(keys, item))
            return results
    else:
        return None


def get_object_fron_key_value(keys, item):
    obj = {}
    for key in keys:
        obj[key] = item[key]
    return obj
