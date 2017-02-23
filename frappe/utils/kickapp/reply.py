from __future__ import unicode_literals

import frappe
import re
import frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _
import json
from frappe.utils.kickapp.helper import format_response


@frappe.whitelist()
def get_all_users():
    return frappe.get_all('User',
                          ["email", "first_name", "last_name", "last_active"])


@frappe.whitelist()
def get_last_active_by_email(email):
    return frappe.get_all('User', ["last_active"], filters={"email": email})


@frappe.whitelist()
def get_users_in_group(room):
    chat_room = frappe.get_all(
        'Chat Room', ["name, room_name"], filters={"room_name": room})
    if len(chat_room) > 0:
        return frappe.get_all('Chat User', ["title", "email", "number"], filters={"parent": chat_room[0].name})


''' Call this for every room in Kick app when app is first launched'''

@frappe.whitelist()
def get_message_for_first_time(obj):
    chats = []

    room = str(obj.room)
    is_bot = str(obj.is_bot).lower()
    last_time = str(obj.last_login_time + '.123456')

    chat_room = frappe.get_all(
        'Chat Room', ["name, room_name"], filters={"room_name": room})

    if len(chat_room) > 0:

        if is_bot == 'true':
            chats = frappe.get_all('Chat Bot', ["bot_name", "text", "list_items", "info", "action"],
                                   filters={"parent": chat_room[0].name, "modified": (">", last_time)})

        else:
            chats = frappe.get_all('Chat Message', ["user_name", "user_id", "is_alert", "text"],
                                   filters={"parent": chat_room[0].name, "modified": (">", last_time)})

        frappe.publish_realtime(event='message_from_server', message=format_response(
            is_bot, chats, room), room=room)


@frappe.whitelist()
def set_user_in_room(room, users):

    chat_room = frappe.get_all(
        'Chat Room', ["name, room_name"], filters={"room_name": room})

    if len(chat_room) < 1:
        chat_room = create_and_save_room_object(room, 'false')

    for user in users:
        create_and_save_user_object(chat_room[0].name, user)


@frappe.whitelist()
def send_message_and_get_reply(obj):

    room = str(obj.room)
    is_bot = str(obj.is_bot).lower()
    query = obj.query

    chats = save_message_in_database(is_bot, room, query)

    if is_bot == 'true':
        response_data = Engine().get_bot_reply(room, query)
        chats = save_message_in_database('true', room, response_data)

    frappe.publish_realtime(event='message_from_server', message=format_response(
        'false', chats, room), room=room)


def save_message_in_database(is_bot, room, query):

    chat_room = frappe.get_all(
        'Chat Room', ["name, room_name"], filters={"room_name": room})

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

    new_bot_chat.bot_name = query.bot_name
    new_bot_chat.text = query.text
    new_bot_chat.info = query.info
    new_bot_chat.action = query.action
    new_bot_chat.list_items = query.list_items

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

    new_other_chat.save()
    frappe.db.commit()
    return [new_other_chat]


def create_and_save_user_object(parent, user):
    doc_user = frappe.new_doc('Chat User')
    doc_user.parent = parent
    doc_user.parentfield = 'people'
    doc_user.parenttype = 'Chat Room'

    doc_user.title = user.title
    doc_user.email = user.email
    doc_user.number = user.number

    doc_user.save()
    frappe.db.commit()
