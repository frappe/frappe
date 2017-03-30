from __future__ import unicode_literals
import frappe


class Constant(object):

	def __init__(self):
		self.all_doctype_basic_action = ["create", "update", "delete", "get"]

		self.doctype_name = {
			'todo': 'ToDo',
			'note': 'Note',
			'user':'User',
			'employee': 'Employee',
			'customer':'Customer',
			'help': 'Help',
			'issue': 'Issue',
			'chat bot':'Chat Bot',
			'chat user':'Chat User',
			'chat message':'Chat Message',
			'chat room' : 'Chat Room'
			}

		self.doctype_category = {
			'Basic_Bot':["todo", "note", "user"]
			}

		self.doctype_fields = {
			'todo': ["name", "description", "creation", "priority", "status", "owner"],
			'note': ["name", "title", "content", "creation", "owner"],
			'user': ["name", "email", "full_name", "first_name", "last_name", 
				"last_active", "new_password", "bio"],
			'employee':["name", "full_name", "gender", "company","date_of_joining", 
				"date_of_birth", "offer_date", "confirmation_date", "employment_status", 
				"parmanent_address", "current_address"],
			'chat message': ["name", "created_at", "text", "chat_data", "bot_data"],
			'chat user' : ["name", "title", "email", "chat_room"],
			'chat room' : ["name", "room_name", "chat_type", "owner"],
			'chat bot' : ["name", "bot_name", "description", "commands", "is_default", "is_available_in_group"]
			}
		
		self.doctype_actions = {
			'todo': self.all_doctype_basic_action,
			'note': self.all_doctype_basic_action,
			'user':self.all_doctype_basic_action,
			}
		
		self.doctype_list_title_fields = {
			'todo': ["description", "creation"],
			'note': ["title", "creation"],
			'user': ["full_name", "email"],
		}

		self.doctype_editable_fields = {
			'todo': ["description"],
			'note': ["title", "content"],
			'user': ["first_name", "last_name", "email", "new_password", "bio"]
		}
		
		self.doctype_messages = {
			'todo': {
				'create':'Alright, Click the button and enter details.',
				'update':'Here is the list of todos. Click on todo to update.',
				'delete':'Here is the list of todos. Click on todo to delete.',
				'get':'Here is the list of todos. Click on todo to get information.',
				'create_':'A new todo has been created. Click on button to view infomation.',
				'update_':'Todo has been updated. Click on button to view infomation.',
				'delete_':'Todo has been deleted.'
			},
			'note': {
				'create':'Alright, Click the button and enter details.',
				'get':'Here is the list of notes. Click on note to get information.',
				'create_':'A new note has been created. Click on button to view infomation.',
				'update_':'Note has been updated. Click on button to view infomation.',
				'delete_':'Note has been deleted.'
			},
			'user': {
				'create':'Alright, Click the button and enter details.',
				'get':'Here is the list of users. Click on to get information.',
				'create_':'A new user has been created. Click on button to view infomation.',
				'update_':'User has been updated. Click on button to view infomation.',
				'delete_':'User has been deleted.'
			},
			}

	def get_doctype_name_from_bot_name(self, bot_name):
		return self.doctype_name.get(bot_name.lower(), "Error")

	def get_class_from_bot_name(self, bot_name):
		for key, value in self.doctype_category.items():
			if bot_name.lower() in value:
				return key
		return 'Error'

	def get_doctype_fields_from_bot_name(self, bot_name):
		return self.doctype_fields.get(bot_name.lower(), [])

	def get_doctype_actions_from_bot_name(self, bot_name):
		return self.doctype_actions.get(bot_name.lower(), [])

	def get_messages_from_bot_name(self, bot_name):
		return self.doctype_messages.get(bot_name.lower(), {})

	def get_mapped_list(self, bot_name, items):
		if len(items) < 1:
			return []
		bot_name = bot_name.lower()
		mapped_items = []
		for item in items:
			mapped_items.append(self.create_obj(bot_name, item))
		return mapped_items
	
	def create_obj(self, bot_name, item):
		obj = {}
		for key in item.keys():
			value = ''
			if item[key] and len(str(item[key])) > 0:
				if(key == "creation"):
					value = str(item[key]).split('.')[0]
				else:
					value = item[key]
			else:
				value = item[key]
			
			obj[key] = frappe._dict({
				"fieldtype":self.get_field_type(bot_name, key),
				"fieldvalue":value,
				"is_req": self.is_required(bot_name, key),
				"list_title_field" : self.get_list_title_field(bot_name, key),
				"is_editable" : self.is_editable(bot_name, key)
			})
		return obj

	def get_field_type(self, bot_name, fieldname):
		desc = frappe.db.sql('desc `tab{0}`'.format(self.get_doctype_name_from_bot_name(bot_name)))
		return filter(lambda x : x[0] == fieldname, desc)[0][1].split('(')[0]
	
	def is_required(self, bot_name, fieldname):
		x = filter(lambda x : x.fieldname == fieldname,
			[i for i in frappe.get_meta(self.get_doctype_name_from_bot_name(bot_name)).fields])
		if x and len(x) > 0:
			return int(x[0].reqd)
		return 0

	def get_list_title_field(self, bot_name, fieldname):
		list_title_fields = self.doctype_list_title_fields.get(bot_name)
		if fieldname in list_title_fields:
			return list_title_fields.index(fieldname) + 1
		return 0
	
	def is_editable(self, bot_name, fieldname):
		if fieldname in self.doctype_editable_fields.get(bot_name):
			return 1
		return 0
	
	def get_dummy_list(self, bot_name):
		fields = self.get_doctype_fields_from_bot_name(bot_name.lower())
		mapped_items = []
		obj = {}
		for f in fields:
			obj[f] = ''
		mapped_items.append(self.create_obj(bot_name.lower(), obj))
		return mapped_items