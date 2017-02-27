from __future__ import unicode_literals

import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
import json
from frappe.utils.kickapp.helper import format_response,\
    format_info_before_adding_to_database, format_list_items_before_adding_to_database, format_action_before_adding_to_database
from frappe.utils.kickapp.engine import Engine


@frappe.whitelist()
def get_all_users():
    return frappe.get_all('User',
                          ["email", "first_name", "last_name", "last_active"])


@frappe.whitelist()
def get_last_active_by_email(email):
    return frappe.get_all('User', ["last_active"], filters={"email": email})


@frappe.whitelist()
def set_user_in_global_chat_room(obj):
    obj = frappe._dict(json.loads(obj))
    room = str(obj.room)
    user = obj.user
    chat_room = frappe.get_all(
        'Chat Room', ["name", "room_name"], filters={"room_name": room})
    if len(chat_room) < 1:
        chat_room = create_and_save_room_object(room, 'false')
    email = frappe._dict(user).email
    user_data = frappe.get_all(
        'Chat User', ["email"], filters={"email": email})
    if len(user_data) < 1:
        create_and_save_user_object(chat_room[0].name, user)


@frappe.whitelist()
def get_users_in_group(room):
    room = str(room)
    chat_room = frappe.get_all(
        'Chat Room', ["name, room_name"], filters={"room_name": room})
    if len(chat_room) > 0:
        return frappe.get_all('Chat User', ["title", "email", "number"], filters={"parent": chat_room[0].name})


''' Call this for every room in Kick app when app is first launched'''


@frappe.whitelist()
def get_message_for_first_time(mail_id):
    chats = []
    filters = {}
    last_time = None
    user = frappe.get_all('User', ["last_active"], filters={
                          "email": mail_id})
    if len(user) > 0:
        last_time = str(user[0].last_active)
        room_list = frappe.get_all(
            'Chat Room', ["name", "room_name", "is_bot"])
        for room in room_list:
            user_data = frappe.get_all('Chat User', ["email", "title", "number"], filters={
                                       "parent": room.name, "email": mail_id})
            if len(user_data) > 0:
                filters = {"parent": room.name, "created_at": (">", last_time)}
                if room.is_bot == 'true':
                    items = frappe.get_all('Chat Bot', ["bot_name", "text", "list_items", "info", "action", "created_at"],
                                           filters=filters)
                    if len(items) > 0:
                        messages = format_response('true', items, room)
                        for message in messages:
                            chats.append(message)
                else:
                    items = frappe.get_all('Chat Message', ["user_name", "user_id", "is_alert", "text", "chat_title", "chat_type", "created_at"],
                                           filters=filters)
                    if len(items) > 0:
                        messages = format_response('false', items, room)
                        for message in messages:
                            chats.append(message)

    # objs = query.objs
    # for obj in objs:
    #     obj = frappe._dict(obj)
    #     room = str(obj.room)
    #     is_bot = str(obj.is_bot).lower()
    #     chat_room = frappe.get_all(
    #         'Chat Room', ["name, room_name"], filters={"room_name": room})
    #     if len(chat_room) > 0:
    #         if last_time != None:
    #             filters = {"parent": chat_room[
    #                 0].name, "created_at": (">", last_time)}
    #         else:
    #             filters = {"parent": chat_room[0].name}

    #         if is_bot == 'true':
    #             items = frappe.get_all('Chat Bot', ["bot_name", "text", "list_items", "info", "action", "created_at"],
    #                                    filters=filters)
    #             if len(items) > 0:
    #                 messages = format_response('true', items, room)
    #                 for message in messages:
    #                     chats.append(message)
    #         else:
    #             items = frappe.get_all('Chat Message', ["user_name", "user_id", "is_alert", "text", "chat_title", "chat_type", "created_at"],
    #                                    filters=filters)
    #             if len(items) > 0:
    #                 messages = format_response('false', items, room)
    #                 for message in messages:
    #                     chats.append(message)
    frappe.publish_realtime(event='message_from_server',
                            message=chats, room=mail_id)


@frappe.whitelist()
def set_users_in_room(obj):
    obj = frappe._dict(json.loads(obj))
    room = str(obj.room)
    users = obj.users
    chat_room = frappe.get_all(
        'Chat Room', ["name", "room_name"], filters={"room_name": room})
    if len(chat_room) < 1:
        chat_room = create_and_save_room_object(room, 'false')
    for user in users:
        email = frappe._dict(user).email
        user_data = frappe.get_all(
            'Chat User', ["email"], filters={"email": email, "parent": chat_room[0].name})
        if len(user_data) < 1:
            create_and_save_user_object(chat_room[0].name, user)


@frappe.whitelist()
def send_message_and_get_reply(obj):
    obj = frappe._dict(json.loads(obj))
    room = str(obj.room)
    is_bot = str(obj.is_bot).lower()

    chats = save_message_in_database(is_bot, room, obj)
    if is_bot == 'true':
        response_data = Engine().get_reply(obj)
        chats = save_message_in_database('true', room, response_data)
    chat_room = frappe.get_all(
        'Chat Room', ["name", "is_bot", "room_name"], filters={"room_name": room})
    print chats
    if len(chat_room) > 0:
        if chat_room[0].is_bot == 'true':
            frappe.publish_realtime(event='message_from_server', message=format_response(
                'true', chats, room), room=room)
        else:
            user_list = frappe.get_all(
                'Chat User', ["email"], filters={"parent": chat_room[0].name})
            for user in user_list:
                frappe.publish_realtime(event='message_from_server', message=format_response(
                    is_bot, chats, room), room=user.email)


def save_message_in_database(is_bot, room, query):
    chat_room = frappe.get_all(
        'Chat Room', ["name", "room_name"], filters={"room_name": room})
    if len(chat_room) < 1:
        chat_room = create_and_save_room_object(room, 'true')

    if is_bot == 'true':
        return create_and_save_bot_object(chat_room[0].name, query)
    else:
        return create_and_save_other_message_object(chat_room[0].name, query)


def create_and_save_room_object(room, is_bot):
    chat_room = frappe.new_doc('Chat Room')

    chat_room.room_name = room
    chat_room.is_bot = is_bot

    chat_room.save()
    frappe.db.commit()
    return [chat_room]


def create_and_save_bot_object(parent, query):
    new_bot_chat = frappe.new_doc('Chat Bot')
    new_bot_chat.parent = parent
    new_bot_chat.parentfield = 'bot'
    new_bot_chat.parenttype = 'Chat Room'
    query = frappe._dict(query)
    print query
    query_info = frappe._dict(query.info)
    query_action = frappe._dict(query.action)
    query_list_items = frappe._dict(query.list_items)

    new_bot_chat.bot_name = query.bot_name
    new_bot_chat.text = query.text
    new_bot_chat.created_at = str(query.created_on + '.123456')

    new_bot_chat.info = format_info_before_adding_to_database(
        query_info.button_text, query_info.is_interactive_chat, query_info.is_interactive_list)
    new_bot_chat.action = format_action_before_adding_to_database(
        query_action.action_on_button_click, query_action.action_on_list_item_click)
    new_bot_chat.list_items = format_list_items_before_adding_to_database(
        query_list_items.action_on_internal_item_click, query_list_items.list_items)

    new_bot_chat.save()
    frappe.db.commit()
    return [new_bot_chat]


def create_and_save_other_message_object(parent, query):
    new_other_chat = frappe.new_doc('Chat Message')
    new_other_chat.parent = parent
    new_other_chat.parentfield = 'message'
    new_other_chat.parenttype = 'Chat Room'

    new_other_chat.user_name = query.user_name
    new_other_chat.user_id = query.user_id
    new_other_chat.is_alert = query.is_alert
    new_other_chat.text = query.text
    new_other_chat.chat_title = query.chat_title
    new_other_chat.chat_type = query.chat_type
    new_other_chat.created_at = str(query.created_on + '.123456')

    new_other_chat.save()
    frappe.db.commit()
    return [new_other_chat]


def create_and_save_user_object(parent, user):
    doc_user = frappe.new_doc('Chat User')
    doc_user.parent = parent
    doc_user.parentfield = 'people'
    doc_user.parenttype = 'Chat Room'
    user = frappe._dict(user)

    doc_user.title = user.title
    doc_user.email = user.email
    doc_user.number = user.number

    doc_user.save()
    frappe.db.commit()
