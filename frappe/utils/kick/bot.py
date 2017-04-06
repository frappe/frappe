from __future__ import unicode_literals
import frappe, re
import frappe.utils
from frappe import _
from frappe.utils.kick.constant import *

class Bot(object):
	
	def call_method_based_on_action(self,action, doctype, tables, params):
		class_name = action_mapper.get(action)
		
		self.error_message(doctype, tables, params) if class_name \
			else getattr(self, class_name)(doctype, tables, params)
	
	def basic_replies(self, doctype, params, tables):
		pass

	def create_doc(self, doctype, params, tables):
		pass
	
	def delete_doc(self, doctype, params, tables):
		pass
	
	def update_doc(self, doctype, params, tables):
		pass
	
	def	get_doc(self, doctype, params, tables):
		pass

	def count_docs(self, doctype, params, tables):
		pass
	
	def error_message(self, doctype, params, tables, msg="Something went wrong, Please try in a little bit."):
		pass
	
	# def get_message(self, msg="Something went wrong, Please try in a little bit.", bot_data = None):
	# 	# obj = self.obj
	# 	# obj.created_at = self.get_created_at()
	# 	# obj.text = msg
	# 	# obj.chat_data = None
	# 	# obj.bot_data = self.get_bot_data() if bot_data is None else bot_data
	# 	# return obj
	# 	pass
	
	def get_bot_data(self):
		pass
	