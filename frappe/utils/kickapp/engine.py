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
		except Exception, e:
			print e
			reply = getattr(Bot_Module, 'Base')(obj).get_message(msg=str(e))
		return reply
	
	def load_more(self, query):
		try:
			helper = Helper() 
			class_name = helper.get_doctype_name_from_bot_name(query.bot_name)
			if class_name != 'Error':
				fields = helper.get_doctype_fields_from_bot_name(query.bot_name)
				page_count = str(query.page_count)
				start = (int(page_count) - 1) * 20
				end = start + 20
				email = str(query.email)				
				return helper.get_mapped_list(query.bot_name,
					helper.get_list(class_name, fields, 
						start, end, {"owner":email}))

		except Exception, e:
			print e
		return []