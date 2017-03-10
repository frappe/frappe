from __future__ import unicode_literals
import frappe
import json
import datetime


class Utils(object):
	def save_message_in_database(self, is_bot, room, query):
		chat_room = frappe.db.exists("Chat Room", {"room_name":room})
		if chat_room is None:
			chat_room = self.create_and_save_room_object(room, 'true')
		if is_bot == 'true':
			return self.create_and_save_bot_object(chat_room, query)
		else:
			return self.create_and_save_other_message_object(chat_room, query)

	def create_and_save_room_object(self, room, is_bot):
		chat_room = frappe.new_doc('Chat Room')
		chat_room.room_name = room
		chat_room.is_bot = is_bot
		chat_room.save()
		frappe.db.commit()
		return chat_room.name

	def create_and_save_bot_object(self, parent, query):
		new_bot_chat = frappe.new_doc('Chat Bot')
		new_bot_chat.parent = parent
		new_bot_chat.parentfield = 'bot'
		new_bot_chat.parenttype = 'Chat Room'
		query = frappe._dict(query)
		query_info = frappe._dict(query.info)
		query_action = frappe._dict(query.action)
		query_list_items = frappe._dict(query.list_items)
		new_bot_chat.bot_name = query.bot_name
		new_bot_chat.text = query.text
		new_bot_chat.created_at = str(query.created_on + '.123456')
		new_bot_chat.info = self.format_info_before_adding_to_database(query_info)
		new_bot_chat.action = self.format_action_before_adding_to_database(query_action)
		new_bot_chat.list_items = self.format_list_items_before_adding_to_database(query_list_items)
		new_bot_chat.save()
		frappe.db.commit()
		return [new_bot_chat]

	def create_and_save_other_message_object(self, parent, query):
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

	def create_and_save_user_object(self, parent, user):
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
	
	def create_bot_message_object(self, room, chat):
		print chat
		return {
			"room": room,
			"is_bot": 'true',
			"bot_name": chat.bot_name,
			"created_on": self.get_date(chat.created_at),
			"text": chat.text,
			"action": chat.action,
			"info": chat.info,
			"list_items": chat.list_items
		}

	def format_response(self, is_bot, chats, room):
		if is_bot == 'true':
			return self.format_response_for_bot(chats, room)
		else:
			return self.format_response_for_others(chats, room)


	def format_response_for_bot(self, chats, room):
		results = []
		for chat in chats:
			item = {
				"room": room,
				"is_bot": 'true',
				"bot_name": chat.bot_name,
				"created_on": self.get_date(chat.created_at),
				"text": chat.text,
				"action": chat.action,
				"info": chat.info,
				"list_items": chat.list_items
			}
			results.append(item)
		return results


	def format_response_for_others(self, chats, room):
		results = []
		for chat in chats:
			item = {
				"room": room,
				"is_bot": 'false',
				"created_on": self.get_date(chat.created_at),
				"user_name": chat.user_name,
				"user_id": chat.user_id,
				"text": chat.text,
				"is_alert": chat.is_alert,
				"chat_title": chat.chat_title,
				"chat_type": chat.chat_type
			}
			results.append(item)
		return results


	def format_list_items_before_adding_to_database(self, list_items):
		if list_items and list_items.items:
			return {
				"action_on_internal_item_click": list_items.action_on_internal_item_click,
				"items": self.get_items_from_array(list_items['items'])
			}
		return{
			"action_on_internal_item_click": None,
			"items": None
		}


	def format_action_before_adding_to_database(self, action):
		if action:
			return {
				"base_action": action.base_action,
				"action_on_button_click": action.action_on_button_click,
				"action_on_list_item_click": action.action_on_list_item_click
			}
		else:
			return{
				"base_action": None,
				"action_on_button_click": None,
				"action_on_list_item_click": None
			}


	def format_info_before_adding_to_database(self, info):
		if info:
			return {
				"button_text": info.button_text,
				"is_interactive_chat": info.is_interactive_chat,
				"is_interactive_list": info.is_interactive_list
			}
		else:
			return{
				"button_text": None,
				"is_interactive_chat": None,
				"is_interactive_list": None
			}

	def get_date(self, created_at):
		created_on = str(created_at)
		return created_on.split('.')[0]

	def get_item_as_dict(self, fields, item):
		obj = {}
		fields_list = fields.split(',')
		for index in range(len(fields_list)):
			value = item[index]
			if isinstance(value, datetime.datetime):
				value = self.get_date(value)
			obj[fields_list[index].strip()] = value
		return obj

	def get_items_from_array(self, items):
		results = []
		if items:
			for item in items:
				x = frappe._dict(item)
				keys = x.keys()
				results.append(self.get_object_from_key_value(keys, item))
		return results

	def get_object_from_key_value(self, keys, item):
		obj = {}
		for key in keys:
			if isinstance(item[key], datetime.datetime):
				obj[key] = self.get_date(item[key])
			else:
				obj[key] = item[key]
		return obj