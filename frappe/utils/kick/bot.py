from __future__ import unicode_literals
import frappe, re
from frappe import _
from frappe.utils.kick.query import Query
from frappe.utils.kick.helper import *
from frappe.utils.kick.constant import *

class Bot(object):
	
	def __init__(self, doctype, params, tables):
		self.doctype = doctype
		self.params = params
		self.tables = tables
		self.query = Query(params.query.lower())
		self.user = get_user_info(params.meta.user_email)
	
	def get_reply_from_action(self, action):
		reply = None
		try:
			method_name = action_mapper.get(action)
			reply = self.error_message() if method_name is None \
				else getattr(self, method_name)()
		except Exception, e:
			msg = "Something went wrong, Please try in a little bit.\n" + "Error : " + e
			reply = self.error_message(msg=msg)
		return reply

	def basic_replies(self):
		reply = None
		if self.query.has(['hi', 'hello', "what's", 'hey']):
			reply = self.get_message(msg='Hello {0}'.format(self.user.first_name))
		elif self.query.has(['bye', 'goodbye', 'bi']):
			reply = self.get_message(msg='Bye {0}'.format(self.user.first_name))
		elif self.query.has(['tell a story', 'tell me a story', 'tell story', 'i want story']):
			reply = self.get_message(msg='{0}'.format(get_random_story()))


	def create_doc(self):
		pass
	
	def delete_doc(self):
		pass
	
	def update_doc(self):
		pass
	
	def	get_doc(self):
		pass

	def count_docs(self):
		pass
	
	def error_message(self, msg="Something went wrong, Please try in a little bit."):
		return self.get_message(msg=msg)
	
	def get_message(self, chat_data = None, bot_data = None, msg="Something went wrong, Please try in a little bit."):
		obj = self.params
		obj.text = msg
		obj.created_at = str(datetime.datetime.now()).split('.')[0]
		obj.chat_data = chat_data or self.params.chat_data
		obj.bot_data = bot_data or self.params.bot_data
		return obj

	
