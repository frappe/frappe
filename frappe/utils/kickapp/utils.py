from __future__ import unicode_literals
import frappe
import json
import datetime


def save_message_in_database(chat_room, is_bot, room, query):
	if chat_room is None:
		chat_room = create_and_save_room_object(room, is_bot)
	if is_bot == 'true':
		return create_and_save_bot_object(chat_room, query)
	else:
		return create_and_save_other_message_object(chat_room, query)

def create_and_save_room_object(room, is_bot):
	doc = frappe.new_doc('Chat Room')
	doc.room_name = room
	doc.is_bot = is_bot
	doc.save()
	frappe.db.commit()
	return doc.name

def create_and_save_bot_object(parent, query):
	doc = frappe.new_doc('Chat Bot')
	doc.parentfield = 'bot'
	doc.parent = parent
	doc.parenttype = 'Chat Room'
	for key, value in query.items():
		if key == 'created_on':
			doc.set('created_at', str(value + '.123456'))
		else:
			doc.set(key, value)
	doc.save()
	frappe.db.commit()
	return [doc]
	# new_bot_chat.parent = parent
	# new_bot_chat.parentfield = 'bot'
	# new_bot_chat.parenttype = 'Chat Room'
	# query = frappe._dict(query)
	# query_info = frappe._dict(query.info)
	# query_action = frappe._dict(query.action)
	# query_list_items = frappe._dict(query.list_items)
	# new_bot_chat.bot_name = query.bot_name
	# new_bot_chat.text = query.text
	# new_bot_chat.created_at = str(query.created_on + '.123456')
	# new_bot_chat.info = self.format_info_before_adding_to_database(query_info)
	# new_bot_chat.action = self.format_action_before_adding_to_database(query_action)
	# new_bot_chat.list_items = self.format_list_items_before_adding_to_database(query_list_items)
	# new_bot_chat.save()
	# frappe.db.commit()
	# return [new_bot_chat]

def create_and_save_other_message_object(parent, query):
	doc = frappe.new_doc('Chat Message')
	doc.parentfield = 'message'
	doc.parent = parent
	doc.parenttype = 'Chat Room'
	for key, value in query.items():
		if key == 'created_on':
			doc.set('created_at', str(value + '.123456'))
		else:
			doc.set(key, value)
	doc.save()
	frappe.db.commit()
	return [doc]
	# new_other_chat = frappe.new_doc('Chat Message')
	# new_other_chat.parent = parent
	# new_other_chat.parentfield = 'message'
	# new_other_chat.parenttype = 'Chat Room'
	# new_other_chat.user_name = query.user_name
	# new_other_chat.user_id = query.user_id
	# new_other_chat.is_alert = query.is_alert
	# new_other_chat.text = query.text
	# new_other_chat.chat_title = query.chat_title
	# new_other_chat.chat_type = query.chat_type
	# new_other_chat.created_at = str(query.created_on + '.123456')
	# new_other_chat.save()
	# frappe.db.commit()
	#return [new_other_chat]

def create_and_save_user_object(parent, user):
	doc = frappe.new_doc('Chat User')
	doc.parentfield = 'message'
	doc.parent = parent
	doc.parenttype = 'Chat Room'
	for key, value in user.items():
		if key == 'created_on':
			doc.set('created_at', str(value + '.123456'))
		else:
			doc.set(key, value)
	doc.save()
	frappe.db.commit()
	
	# doc_user.title = user.title
	# doc_user.email = user.email
	# doc_user.number = user.number
	# doc_user.save()
	# frappe.db.commit()


def create_bot_message_object(room, chat):
	return {
		"room": room,
		"is_bot": 'true',
		"bot_name": chat.bot_name,
		"created_on": get_date(chat.created_at),
		"text": chat.text,
		"action": chat.action,
		"info": chat.info,
		"list_items": chat.list_items
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
			"created_on": get_date(chat.created_at),
			"text": chat.text,
			"action": chat.action,
			"info": chat.info,
			"list_items": chat.list_items
		}
		results.append(item)
	return results


def format_response_for_others(chats, room):
	results = []
	for chat in chats:
		item = {
			"room": room,
			"is_bot": 'false',
			"created_on": get_date(chat.created_at),
			"user_name": chat.user_name,
			"user_id": chat.user_id,
			"text": chat.text,
			"is_alert": chat.is_alert,
			"chat_title": chat.chat_title,
			"chat_type": chat.chat_type
		}
		results.append(item)
	return results


def get_date(created_at):
	created_on = str(created_at)
	return created_on.split('.')[0]

def get_item_as_dict(fields, item):
	obj = {}
	fields_list = fields.split(',')
	for index in range(len(fields_list)):
		value = item[index]
		if isinstance(value, datetime.datetime):
			value = get_date(value)
		obj[fields_list[index].strip()] = value
	return obj

def get_items_from_array(items):
	results = []
	if items:
		for item in items:
			x = frappe._dict(item)
			keys = x.keys()
			results.append(get_object_from_key_value(keys, item))
	return results

def get_object_from_key_value(keys, item):
	obj = {}
	for key in keys:
		if isinstance(item[key], datetime.datetime):
			obj[key] = get_date(item[key])
		else:
			obj[key] = item[key]
	return obj