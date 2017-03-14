from __future__ import unicode_literals


class Constant(object):

	def __init__(self):
		self.all_doctype_basic_action = ["create", "update", "delete", "get"]

		self.doctype_name = {
			'todo': 'ToDo',
			'note': 'Note',
			'help': 'Help',
			'chat': 'Chat',
			'issue': 'Issue'
			}

		self.doctype_category = {
			'Basic_Bot':["todo", "note"]
			}

		self.doctype_fields = {
			'todo': ["name", "description", "creation", "priority", "status"],
			'note': ["name", "content", "creation", "_comments", "_assign"],
			'chat message':["user_name", "user_id", "is_alert", "text", "chat_title", "chat_type", "created_at"]
			}
		
		self.doctype_actions = {
			'todo': self.all_doctype_basic_action,
			'note': self.all_doctype_basic_action
			}
		
		self.doctype_messages = {
			'todo': {
				'create':'Alright, Enter description of todo.',
				'update':'Here is the list of todos. Click on todo to update.',
				'delete':'Here is the list of todos. Click on todo to delete.',
				'get':'Here is the list of todos. Click on todo to get information.',
				'create_':'A new todo has been created. Click on button to view infomation.',
				'update_':'Todo has been updated. Click on button to view infomation.',
				'delete_':'Todo has been deleted. Click on button to view infomation.'
			},
			'note': {
				'create':'Alright, Enter new text.',
				'update':'Here is the list of notes. Click on note to update.',
				'delete':'Here is the list of notes. Click on note to delete.',
				'get':'Here is the list of notes. Click on note to get information.',
				'create_':'A new note has been created. Click on button to view infomation.',
				'update_':'Note has been updated. Click on button to view infomation.',
				'delete_':'Note has been deleted. Click on button to view infomation.'
			}
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