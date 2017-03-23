from __future__ import unicode_literals
import datetime
import frappe
from frappe.utils.kickapp.helper import Helper
import frappe.utils.kickapp.bot as Bot_Module 

class Engine(object):
	def get_reply(self, obj):
		reply = {}
		try:
			class_name = Helper().get_class_from_bot_name(obj.bot_data.bot_name)
			if class_name == 'Error':
				reply = getattr(Bot_Module, 'Base')(obj).get_message()
			else:
				reply = getattr(Bot_Module, class_name)(obj).get_results()
		except Exception, exce:
			print exce
			e = str(exce)
			if e.find('No permission') > -1:
				reply = getattr(Bot_Module, 'Base')(obj).get_message("You dont have permission to perform tasks.")
			else:
				reply = getattr(Bot_Module, 'Base')(obj).get_message()
		return reply
	
	def load_more(self, query):
		try:
			class_name = Helper().get_doctype_name_from_bot_name(query.bot_name)
			if class_name != 'Error':
				fields = Helper().get_doctype_fields_from_bot_name(query.bot_name)
				page_count = str(query.page_count)
				start = (int(page_count) - 1) * 20
				end = start + 20
				email = str(query.email)
				items = Helper().get_list(class_name, fields, start, end, {"owner":email})
				reply = getattr(Bot_Module, class_name)().map_list(items)
				return reply
		except Exception, exce:
			print exce
		return []