from __future__ import unicode_literals
import frappe
from frappe.utils.kickapp.helper import *
from frappe.utils.kickapp.engine import Engine
from frappe.utils.kickapp.utils import *


class Reply(object):

	def __init__(self):
		self.helper = Helper()

	def get_all_users(self, email):
		return self.helper.get_list('User', fields=["email", "full_name", "last_active"], get_all=True)

	def get_users_in_room(self, room):
		chat_room = frappe.db.exists("Chat Room", {"room_name": str(room)})
		if chat_room is not None:
			return self.helper.get_list('Chat User', 
				fields=["full_name", "email", "number"], 
				filters={"chat_room": chat_room}, get_all=True)
		else:
			return []
	""" baad mein bahi """
	def load_more(self, query):
		return Engine().load_more(query)

	def set_users_in_room(self, obj):
		room = str(obj.room)
		users = obj.users
		chat_room = frappe.db.exists("Chat Room", {"room_name": room})
		if chat_room is None:
			chat_room = create_and_save_room_object(room, False)
		i = 0
		while i <= len(users):
			if i == len(users):
				break
			user = frappe._dict(users[i])
			user_data = frappe.db.exists("Chat User", {"email": user.email, "chat_room": chat_room})
			if user_data is None:
				create_and_save_user_object(chat_room, user)
			i += 1
		return 'Added Users'

	def get_message_for_first_time(self, obj):
		mail_id = str(obj.mail_id)
		rooms = obj.rooms
		last_message_times = obj.last_message_times
		self.get_message_from_rooms_recursively([], mail_id, rooms, last_message_times, 0, 40)

	def get_message_from_rooms_recursively(self, chats, mail_id, rooms, last_message_times, limit_start, limit_page_length):
		room_list = self.helper.get_list('Chat Room', ["name", "room_name", "is_bot"], 
			limit_start=limit_start, limit_page_length=limit_page_length)
		if len(room_list) > 0:
			for room in room_list:
				if frappe.db.exists('Chat User', {"chat_room": room.name, "email": mail_id}) is not None:
					filters = {"chat_room":room.name}
					index = -1
					try:
						index = rooms.index(room.room_name)
					except Exception, e:
						index = -1
					if index > -1:
						last_message_time = last_message_times[index]
						if last_message_time is not None:
							last_message_time = str(str(last_message_time) + '.123456')
							filters = {"chat_room":room.name, "created_at":(">", last_message_time)}
					
					chats = self.helper.get_list('Chat Message', 
								self.helper.get_doctype_fields_from_bot_name('Chat Message'), 
								filters=filters, get_all=True)
			
			frappe.publish_realtime(event='message_from_server', 
				message=format_response(room.is_bot, chats, room.room_name), 
				room=mail_id)
			
			if len(room_list) > 19:
				limit_start = limit_start + 40
				limit_page_length = limit_page_length + 40
				self.get_message_from_rooms_recursively([], mail_id, rooms, 
					last_message_times, limit_start, limit_page_length)
		else:
			frappe.publish_realtime(event='message_from_server', 
				message=[], 
				room=mail_id)

	def send_message_and_get_reply(self, query):
		
		obj = frappe._dict(query.obj)
		meta = frappe._dict(obj.meta)
		room = str(meta.room)
		is_bot = meta.is_bot
		user_id = str(meta.user_id)

		chat_room = frappe.db.exists("Chat Room", {"room_name":room})
		chats = save_message_in_database(chat_room, is_bot, room, obj)
		if is_bot:
			response_data = Engine().get_reply(obj)
			chats = save_message_in_database(chat_room, is_bot, room, response_data)
			frappe.publish_realtime(event='message_from_server', 
				message=format_response(is_bot, chats, room), 
				room=user_id)
		else:
			for user in self.helper.get_list('Chat User', ["email"], filters={"chat_room":chat_room}, get_all=True):
				if not (user_id == user.email):
					frappe.publish_realtime(event='message_from_server', 
						message= format_response(is_bot, chats, room), 
						room=user.email)
