from __future__ import unicode_literals
import frappe
import json
import datetime


def save_message_in_database(chat_room, is_bot, room, query):
	if chat_room is None:
		chat_room = create_and_save_room_object(room, is_bot)
	return create_and_save_message_object(chat_room, query)


def create_and_save_room_object(room, is_bot):
	doc = frappe.new_doc('Chat Room')
	doc.room_name = room
	doc.is_bot = is_bot
	doc.save()
	frappe.db.commit()
	return doc.name


def create_and_save_message_object(chat_room, query):
	doc = frappe.new_doc('Chat Message')
	doc.chat_room = chat_room
	for key, value in query.items():
		if key == 'meta':
			continue
		elif key == 'created_on':
			doc.set('created_at', str(value + '.123456'))
		else:
			doc.set(key, value)
	doc.save()
	frappe.db.commit()
	return [doc]


def create_and_save_user_object(chat_room, user):
	doc = frappe.new_doc('Chat User')
	doc.chat_room = chat_room
	for key, value in user.items():
		doc.set(key, value)
	doc.save()
	frappe.db.commit()


def create_bot_message_object(room, chat):
	return {
		"meta": {
			"room": room,
			"is_bot": True
		},
		"created_on": get_date(chat.created_at),
		"text": chat.text,
		"chat_data": chat.chat_data,
		"bot_data": chat.bot_data,
	}

def format_response(is_bot, chats, room):
	results = []
	for chat in chats:
		item = {
			"meta": {
				"room": room,
				"is_bot": True if is_bot else False
			},
			"created_on": get_date(chat.created_at),
			"text": chat.text,
			"chat_data": chat.chat_data,
			"bot_data": chat.bot_data,
		}
		results.append(item)
	return results


def get_date(created_at):
	created_on = str(created_at)
	return created_on.split('.')[0]


# def get_item_as_dict(fields, item):
# 	obj = {}
# 	fields_list = fields.split(',')
# 	for index in range(len(fields_list)):
# 		value = item[index]
# 		if isinstance(value, datetime.datetime):
# 			value = get_date(value)
# 		obj[fields_list[index].strip()] = value
# 	return obj


# def get_items_from_array(items):
# 	results = []
# 	if items:
# 		for item in items:
# 			x = frappe._dict(item)
# 			keys = x.keys()
# 			results.append(get_object_from_key_value(keys, item))
# 	return results


# def get_object_from_key_value(keys, item):
# 	obj = {}
# 	for key in keys:
# 		if isinstance(item[key], datetime.datetime):
# 			obj[key] = get_date(item[key])
# 		else:
# 			obj[key] = item[key]
# 	return obj
