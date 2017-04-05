from __future__ import unicode_literals
import frappe
from frappe.utils.kickapp.constant import Constant

class Helper(object):
	def __init__(self):
		self.constant = Constant()

	def get_doctype_name_from_bot_name(self, bot_name):
		return self.constant.get_doctype_name_from_bot_name(bot_name)

	def get_doctype_fields_from_bot_name(self, bot_name):
		return self.constant.get_doctype_fields_from_bot_name(bot_name)

	def get_doctype_actions_from_bot_name(self, bot_name):
		return self.constant.get_doctype_actions_from_bot_name(bot_name)

	def get_class_from_bot_name(self, bot_name):
		return self.constant.get_class_from_bot_name(bot_name)

	def get_messages_from_bot_name(self, bot_name):
		return self.constant.get_messages_from_bot_name(bot_name)
	
	def get_mapped_list(self, bot_name, items):
		return self.constant.get_mapped_list(bot_name, items)
	
	def get_dummy_list(self, bot_name):
		return self.constant.get_dummy_list(bot_name)
	
	def get_doctype_fields(self, bot_name):
		return self.constant.get_doctype_fields(bot_name)
	
	def get_dict(self, doctype, keys, item):
		obj = frappe._dict({})
		obj["doctype"] = doctype
		for key in keys:
			obj[key] = item[key]["fieldvalue"]
		return obj
	
	def get_list(self, doctype, fields, limit_start=0, limit_page_length=20, filters=None, get_all=False):
		if get_all:
			return frappe.get_list(doctype, fields=fields, filters=filters)
		elif filters is not None:
			return frappe.get_list(doctype, fields=fields, limit_start=limit_start, limit_page_length=limit_page_length, filters=filters)
		return frappe.get_list(doctype, fields=fields, limit_start=limit_start, limit_page_length=limit_page_length)

	def get_all_items_using_direct_query(self, doctype, fields, filters=None):
		query = """select {0} from `tab{1}`""".format(fields, doctype)
		if filters is not None:
			query = query + """ where """ + filters
		return frappe.db.sql(query + ';')
