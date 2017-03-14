from __future__ import unicode_literals
import datetime
import frappe
import json
from frappe.utils.kickapp.helper import Helper
from frappe.utils.kickapp.utils import *
from frappe.utils.kickapp.query import Query

class Engine(object):
	def get_reply(self, obj):
		reply = {}
		try:
			class_name = Helper().get_class_from_bot_name(obj.bot_name)
			if class_name == 'Error':
				reply = Base(obj).get_error_message()
			else:
				reply = globals()[class_name](obj).get_results()
		except Exception, exce:
			print exce
			e = str(exce)
			if e.find('No permission') > -1:
				reply = Base(obj).get_error_message("You dont have permission to perform tasks.")
			else:
				reply = Base(obj).get_error_message()
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
				return globals()[class_name]().map_list(items)
		except Exception, exce:
			print exce
		return []

class Base(object):

	def __init__(self, obj):
		self.obj = obj
		self.query = Query(obj.bot_name)
		self.helper = Helper()

	def get_error_message(self, msg="Something went wrong, Please try in a little bit."):
		obj = self.obj
		obj.text = msg
		obj.created_at = self.get_created_at()
		obj.action = self.prepare_action()
		obj.info = self.prepare_info()
		obj.list_items = self.prepare_list_items()
		return create_bot_message_object(obj.room, obj)

	def get_action_by_text(self, text):
		return self.query.get_action_from_text(text)

	def get_list(self, doctype, fields, filters):
		return self.helper.get_list(doctype, fields, 0, 3, filters)

	def get_created_at(self):
		return get_date(str(datetime.datetime.now()))

	def prepare_action(self, base_action=None):
		return {
			"base_action": base_action,
		}

	def prepare_info(self, button_text=None, is_interactive_chat=False, is_interactive_list=False):
		return {
			"button_text": button_text,
			"is_interactive_chat": is_interactive_chat,
			"is_interactive_list": is_interactive_list
		}

	def prepare_list_items(self, items=[]):
		return {
			"items": items
		}


class Basic_Bot(Base):

	def __init__(self, obj):
		Base.__init__(self, obj)
		self.bot_name = obj.bot_name
		self.fields = self.helper.get_doctype_fields_from_bot_name(self.bot_name)
		self.messages = self.helper.get_messages_from_bot_name(self.bot_name)
		self.doctype = self.helper.get_doctype_name_from_bot_name(self.bot_name)

	def get_results(self):
		method = self.get_method()
		if method == 'error':
			return self.get_error_message("Something went wrong, please try a diffrent query")
		else:
			return getattr(self, method)()

	def prepare_obj(self, method_name, action, info, list_items):
		obj = self.obj
		obj.text = self.messages.get(method_name)
		obj.created_at = self.get_created_at()
		obj.action = action
		obj.info = info
		obj.list_items = list_items
		return obj
	
	def map_list(self, items):
		return globals()[self.doctype]().map_list(items)

	def get_method(self):
		obj = self.obj
		base_action = frappe._dict(obj.action).base_action
		item_id = obj.item_id
		if base_action == 'create_':
			return 'create_'
		elif base_action is not None and item_id is not None:
			return base_action.lower()
		return self.get_action_by_text(obj.text).lower()

	def create(self):
		action = self.prepare_action(base_action='create_')
		info = self.prepare_info()
		list_items = self.prepare_list_items()
		return self.prepare_obj('create', action, info, list_items)

	def update(self):
		items = self.get_list(self.doctype, self.fields, filters={"owner": self.obj.user_id})
		action = self.prepare_action('update_')
		info = self.prepare_info(button_text='load more', is_interactive_list=True)
		list_items = self.prepare_list_items(self.map_list(items))
		return self.prepare_obj('update', action, info, list_items)
		
	def delete(self):
		items = self.get_list(self.doctype, self.fields, filters={"owner": self.obj.user_id})
		action = self.prepare_action('delete_')
		info = self.prepare_info(button_text='load more', is_interactive_list=True)
		list_items = self.prepare_list_items(self.map_list(items))
		return self.prepare_obj('delete', action, info, list_items)

	def get(self):
		items = self.get_list(self.doctype, self.fields, filters={"owner": self.obj.user_id})
		action = self.prepare_action()
		info = self.prepare_info(button_text='load more', is_interactive_list=True)
		list_items = self.prepare_list_items(self.map_list(items))
		return self.prepare_obj('get', action, info, list_items)

	def create_(self):
		data =  globals()[self.doctype]().create_(self.doctype, self.obj)
		if data.is_success:
			items = self.get_list(self.doctype, self.fields, data.filters)
			action = self.prepare_action()
			info = self.prepare_info(button_text='view info', is_interactive_chat=True)
			list_items = self.prepare_list_items(self.map_list(items))
			return self.prepare_obj('create_', action, info, list_items)
		else:
			return self.get_error_message()

	def update_(self):
		data =  globals()[self.doctype]().update_(self.doctype, self.obj)
		if data.is_success:
			items = self.get_list(self.doctype, self.fields, data.filters)
			action = self.prepare_action()
			info = self.prepare_info(button_text='view info', is_interactive_chat=True)
			list_items = self.prepare_list_items(self.map_list(items))
			return self.prepare_obj('update_', action, info, list_items)
		else:
			return self.get_error_message()
		

	def delete_(self):
		filters = {"name": self.obj.item_id, "owner": self.obj.user_id}
		try:
			items = self.get_list(self.doctype, self.fields, filters)
			if len(items) > 0:
				frappe.delete_doc(self.doctype, self.obj.item_id)
				frappe.db.commit()
				action = self.prepare_action()
				info = self.prepare_info(button_text='view info', is_interactive_chat=True)
				list_items = self.prepare_list_items(self.map_list(items))
				return self.prepare_obj('delete_', action, info, list_items)
			else:
				return self.get_error_message("Looks like item already deleted from database.")
		except Exception, e:
			print e
			return self.get_error_message()


class Note(object):

	def map_list(self, items):
		new_list = []
		for item in items:
			new_list.append({
				"id": item.name,
				"text": item.name if item.content is None else item.content,
				"creation": str(item.creation).split('.')[0]
			})
		return new_list

	def create_(self, doctype, obj):
		filters = None
		is_success = False
		try:
			title = obj.text[0:9] if len(obj.text) > 10 else obj.text 
			note_doc = frappe.get_doc({"doctype":doctype, "title": title})
			note_doc.content = obj.text
			note_doc.owner = obj.user_id
			note_doc.save()
			frappe.db.commit()
			filters = {"name": note_doc.name, "owner": obj.user_id}
			is_success = True
		except Exception, e:
			print e
			filters = None
			is_success = False
		return frappe._dict({
			"is_success" : is_success,
			"filters": filters
		})

	def update_(self, doctype, obj):
		filters = None
		is_success = False
		try:
			item_id = obj.item_id
			frappe.set_value(doctype, item_id, "content", obj.text)
			frappe.db.commit()
			filters = {"name": item_id, "owner": obj.user_id}
			is_success = True
		except Exception, e:
			print e
			filters = None
			is_success = False
		return frappe._dict({
			"is_success" : is_success,
			"filters": filters
		})

class ToDo(object):

	def map_list(self, items):
		new_list = []
		for item in items:
			new_list.append({
				"id": item.name,
				"text": item.description,
				"creation": str(item.creation).split('.')[0]
			})
		return new_list

	def create_(self, doctype, obj):
		filters = None
		is_success = False
		try:
			todo_doc = frappe.new_doc(doctype)
			todo_doc.description = obj.text
			todo_doc.owner = obj.user_id
			todo_doc.save()
			frappe.db.commit()
			filters = {"name": todo_doc.name, "owner": obj.user_id}
			is_success = True
		except Exception, e:
			print e
			filters = None
			is_success = False
		return frappe._dict({
			"is_success" : is_success,
			"filters": filters
		})

	def update_(self, doctype, obj):
		filters = None
		is_success = False
		try:
			item_id = obj.item_id
			frappe.set_value(doctype, item_id, "description", obj.text)
			frappe.db.commit()
			filters = {"name": item_id, "owner": obj.user_id}
			is_success = True
		except Exception, e:
			print e
			filters = None
			is_success = False
		return frappe._dict({
			"is_success" : is_success,
			"filters": filters
		})
