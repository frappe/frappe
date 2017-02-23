from __future__ import unicode_literals
import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
import json

@frappe.whitelist()
def get_dev_port():
    return conf.get("developer_mode"), conf.get('socketio_port')


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
            "bot_name": chat.bot_name,
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
            "user_name": chat.user_name,
            "user_id": chat.user_id,
            "text": chat.text,
            "is_alert": chat.is_alert
        }
        results.append(item)
    return results


def format_list_items_to_json(list_items):
    return json.loads(list_items)


def format_info_to_json(info):
    return json.loads(info)


def format_action_to_json(action):
    return json.loads(action)


''' Format other message before adding to database '''


def format_other_message_before_saving_to_database(user_name, user_id, text, is_alert):
    return {
        "user_name": user_name,
        "user_id":  user_id,
        "text":  text,
        "is_alert":  is_alert
    }


''' Format bot message before adding to database '''


def format_bot_message_before_saving_to_database(bot_name, text, action, info, list_items):
    return {
        "bot_name": bot_name,
        "text": text,
        "action": format_action_before_adding_to_database(action.action_on_button_click, action.action_on_list_item_click),
        "info": format_info_before_adding_to_database(info.button_text, info.is_interactive_chat, info.is_interactive_list),
        "list_items": format_list_items_before_adding_to_database(action.action_on_internal_item_click, list_items)
    }


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
    results = []
    for item in items:
        keys = item.keys()
        results.append(get_object_fron_key_value(keys, items))
    return results


def get_object_fron_key_value(keys, items):
    obj = {}
    for key in keys:
        obj[key] = items[key]
    return obj
