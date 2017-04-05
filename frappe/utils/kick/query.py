from __future__ import unicode_literals
import frappe, re, frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _

class Query(object):
	def __init__(self, query):
		self.query = query
		self.process_query()
	
	def starts_with(self, words):
		for w in words:
			if self.query.startswith(w):
				return True
		return False
	
	def has(self, words):
		for w in words:
			if w in self.query:
				return True
		return False
	
	def strip_words(self, words):
		return (' '.join(filter(lambda x: x.lower() not in words, 
				self.query.split()))).strip()
	
	def process_query(self):
		self.remove_startswith()
		self.remove_endswith()

	def remove_endswith(self):
		self.query = self.query[:-1] if self.query.endswith("?") else self.query
		self.query = self.query[:-1] if self.query.endswith(".") else self.query
		self.query = self.query[:-1] if self.query.endswith(";") else self.query
		self.query = self.query[:-1] if self.query.endswith(":") else self.query
		self.query = self.query[:-1] if self.query.endswith('"') else self.query
	
	def remove_startswith(self):
		self.query = self.query[:-1] if self.query.startswith("?") else self.query
		self.query = self.query[:-1] if self.query.startswith(".") else self.query
		self.query = self.query[:-1] if self.query.startswith(";") else self.query
		self.query = self.query[:-1] if self.query.startswith(":") else self.query
		self.query = self.query[:-1] if self.query.startswith('"') else self.query
	
	def append_open(self, doctype_names):
		contains = filter(lambda x: doctype_names.get(x) is not None ,
			[i for i in doctype_names]) 
		if len(contains) > 0:
			self.query = 'open ' + self.query
	
	def get_simple_msg_reply(self):
		reply_text = "Hi {0}".format(frappe.utils.get_fullname()) \
			if self.starts_with(['hello', 'hi']) else None
		reply_text = "I'm good {0}".format(frappe.utils.get_fullname()) \
			if self.starts_with(['how are you doing', 'how are you']) else None
		reply_text = "I'm kick bot {0}. I'll try to reply your simple queries".format(frappe.utils.get_fullname()) \
			if self.starts_with(['who are you', 'what do you do', 'what you can do']) else None
		reply_text = reply_text if reply_text is not None else \
			"Hi there, something wrong. Try asking like how are you?"
		return reply_text