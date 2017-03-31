from __future__ import unicode_literals
import frappe, re
from frappe.utils.kickapp.helper import Helper

class Query(object):

	def __init__(self, bot_name):
		self.bot_name = bot_name.lower()
		self.actions = Helper().get_doctype_actions_from_bot_name(bot_name)
	
	def has(self, query, words):
		for word in words:
			sub_string = query if len(query) < len(word) else word
			string = query if len(query) > len(word) else word
			if sub_string in string:
				return True

	def get_action_from_text(self, text):
		for x in self.actions:
			all_keywords = self.generate_keyword(x)
			if len(all_keywords) > 0 and self.has(text, all_keywords):
				return x
		return 'error'

	def generate_keyword(self, action):
		if action == 'create':
			return self.create_keywords()
		elif action == 'get':
			return self.get_keywords() 
		else:
			return []

	def create_keywords(self):
		doctype = self.bot_name
		return ['create', 
				'{0} {1}'.format('create new', doctype), 
				'{0} {1}'.format('create a', doctype),
				'{0} {1}'.format('create my', doctype),
				'{0} {1}'.format('create', doctype),
				'{0} {1}'.format('hey create new', doctype),
				'{0} {1}'.format('hey create', doctype),
				'{0} {1}'.format('make new', doctype),
				'{0} {1}'.format('make a', doctype),
				'{0} {1}'.format('make', doctype)]

	def get_keywords(self):
		doctype = self.bot_name
		return ['get', 'list','list all',
				'{0} {1} {2}'.format('list', 'all', doctype),
				'{0} {1}'.format('list', doctype), 
				'{0} {1}'.format('get', doctype),
				'{0} {1}'.format('get all', doctype),
				'{0} {1}'.format('get my', doctype),
				'{0} {1} {2}'.format('get', doctype, 's'),
				'{0} {1} {2}'.format('get all', doctype, 's'),
				'{0} {1} {2}'.format('get my', doctype, 's')]