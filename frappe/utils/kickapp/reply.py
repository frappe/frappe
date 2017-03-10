from __future__ import unicode_literals
import frappe
from frappe.utils.kickapp.helper import Helper
from frappe.utils.kickapp.engine import Engine
from frappe.utils.kickapp.utils import Utils


class Reply(object):
	def __init__(self):
		self.utils = Utils()
		self.helper = Helper()

	def get_all_users(self, email):
		fields = "email, first_name, last_name, last_active"
		user_list = self.helper.get_all_items_using_direct_query('User', fields)
		new_list = []
		for user in user_list:
			x = list(user)
			if x[0].lower() != email.lower():
				new_list.append(self.utils.get_item_as_dict(fields, x))
		return new_list

	def set_users_in_room(self, obj):
		room = str(obj.room)
		users = obj.users
		chat_room = frappe.db.exists("Chat Room", {"room_name":room})
		if chat_room is None:
			chat_room = self.utils.create_and_save_room_object(room, 'false')
		i = 0
		while i <= len(users):
			if i == len(users):
				break
			email = frappe._dict(users[i]).email
			user_data = frappe.db.exists("Chat User", {"email": email, "parent": chat_room})
			if user_data is None:
				self.utils.create_and_save_user_object(chat_room, users[i])
			i += 1
		return 'Added Users'


	def get_users_in_room(self, room):
		room = str(room)
		chat_room = frappe.db.exists("Chat Room", {"room_name":room})
		result = []
		if chat_room is not None:
			fields = "email, title, number"
			filters = "parent='{0}'".format(chat_room)
			user_list = self.helper.get_all_items_using_direct_query('Chat User', fields, filters)
			for user in user_list:
				x = list(user)
				result.append(self.utils.get_item_as_dict(fields, x))
		return result


	def get_message_for_first_time(self, obj):
		print obj
		mail_id = str(obj.mail_id)
		rooms = obj.rooms
		last_message_times = obj.last_message_times
		self.get_message_from_rooms_recursively([], mail_id, rooms, last_message_times, 0, 20)
		

	def get_message_from_rooms_recursively(self, chats, mail_id, rooms, last_message_times, limit_start, limit_page_length):
		room_list = self.helper.get_list('Chat Room', ["name", "room_name", "is_bot"], limit_start, limit_page_length)
		if len(room_list) > 0:
			for room in room_list:
				filters = None
				if frappe.db.exists('Chat User', {"parent": room.name, "email": mail_id}) is not None:
					index = -1
					try:
						index = rooms.index(room.room_name)
					except Exception, e:
						index = -1
					if index > -1:
						last_message_time = last_message_times[index]
						if last_message_time is not None:
							last_message_time = str(str(last_message_time) + '.123456')
							filters = "parent='{0}' and created_at > '{1}'".format(room.name, last_message_time)
						else:
							filters = "parent='{0}'".format(room.name)
					else:
						filters = "parent='{0}'".format(room.name)
					items = []
					fields = "user_name, user_id, is_alert, text, chat_title, chat_type, created_at"
					msg_list = self.helper.get_all_items_using_direct_query('Chat Message', fields, filters)
					for msg in msg_list:
						x = list(msg)
						items.append(frappe._dict(self.utils.get_item_as_dict(fields, x)))
					if len(items) > 0:
						chats = chats + self.utils.format_response('false', items, room.room_name)
			frappe.publish_realtime(event='message_from_server', message=chats, room=mail_id)
			if len(room_list) > 19:
				limit_start = limit_start + 20
				limit_page_length = limit_page_length + 20
				self.get_message_from_rooms_recursively([], mail_id, rooms, last_message_times, limit_start, limit_page_length)
		


	def send_message_and_get_reply(self, query):
		obj = frappe._dict(query.obj)
		room = str(obj.room)
		is_bot = str(obj.is_bot).lower()
		user_id = str(query.user_id)
		chats = self.utils.save_message_in_database(is_bot, room, obj)
		if is_bot == 'true':
			response_data = Engine().get_reply(obj)
			chats = self.utils.save_message_in_database('true', room, response_data)
		chat_room = frappe.db.exists("Chat Room", {"room_name":room})
		if chat_room is not None:
			chat_room = frappe.get_doc('Chat Room', chat_room)
			if chat_room.is_bot == 'true':
				frappe.publish_realtime(event='message_from_server', message=self.utils.format_response('true', chats, room), room=user_id)
			else:
				user_list = self.helper.get_all_items_using_direct_query('Chat User', "email", "parent='{0}'".format(chat_room.name))
				for user in user_list:
					if not (user_id == user[0]):
						frappe.publish_realtime(event='message_from_server', message=self.utils.format_response('false', chats, room), room=user[0])
	
