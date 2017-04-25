from __future__ import unicode_literals
import datetime
import frappe
from frappe.utils.kickapp.helper import Helper
import frappe.utils.kickapp.bot as Bot_Module 
from frappe.desk.notifications import get_notifications


class Engine(object):
	def get_reply(self, obj):
		reply = {}
		try:
			class_name = Helper().get_class_from_bot_name(obj.bot_data.bot_name)
			if class_name == 'Error':
				reply = getattr(Bot_Module, 'Base')(obj).get_message()
			else:
				reply = getattr(Bot_Module, class_name)(obj).get_results()
		except Exception, e:
			print e
			reply = getattr(Bot_Module, 'Base')(obj).get_message(msg=str(e))
		return reply

	def load_more(self, query):
		try:
			helper = Helper() 
			class_name = str(helper.get_doctype_name_from_bot_name(query.bot_name))
			if class_name != 'Error':
				fields = helper.get_doctype_fields_from_bot_name(query.bot_name)
				page_count = str(query.page_count)
				start = (int(page_count) - 1) * 20
				end = start + 20
				email = str(query.email)
				filters = None if class_name == 'Issue' else {"owner":email}
				# return helper.get_list(class_name, fields, start, end, 
				# 	filters)
				return helper.get_mapped_list(query.bot_name,
					helper.get_list(class_name, fields, 
						start, end, filters))
		except Exception, e:
			print e
		return []

	def load_items(self, query):
		try:
			helper = Helper() 
			class_name = str(helper.get_doctype_name_from_bot_name(query.bot_name))
			if class_name != 'Error':
				fields = helper.get_doctype_fields(class_name)
				page_count = str(query.page_count)
				start = (int(page_count) - 1) * 20
				end = start + 20
				email = str(query.email)
				filters = None if class_name == 'Issue' else {"owner":email}
				return helper.get_list(class_name, fields, start, end, 
					filters)
				# return helper.get_mapped_list(query.bot_name,
				# 	helper.get_list(class_name, fields, 
				# 		start, end, {"owner":email}))
		except Exception, e:
			print e
		return []

class AI(Engine):
	
	def __init__(self, query):
		self.query = query
		self.tables = []
		self.prepare_doctype_names(frappe.get_list('DocType', {"istable":0}))
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
	
	def strip_words(self, query, words):
		return (' '.join(filter(lambda x: x.lower() not in words, 
				query.split()))).strip()
	
	def get_doctype(self):
		return self.doctype_names[self.tables[0]]
	
	def prepare_doctype_names(self, doctypes):
		self.doctype_names = {d.name.lower():d.name for d in doctypes}
		self.prepare_tables(doctypes)

	def prepare_tables(self, doctypes):
		self.tables = filter(lambda x: x in self.query or x[:-1] in self.query, 
			[d.name.lower() for d in doctypes])
	
	def process_query(self):
		if self.query.endswith("?"):
			self.query = self.query[:-1]
		contains = filter(lambda x: self.doctype_names.get(x) is not None ,
			[i for i in self.doctype_names]) 
		if len(contains) > 0:
			self.query = 'open ' + self.query
	
	


