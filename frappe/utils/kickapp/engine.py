from __future__ import unicode_literals
import datetime
import frappe
import json
from frappe.utils.kickapp.helper import Helper
from frappe.utils.kickapp.utils import Utils
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
			e = str(exce)
			if e.find('No permission') > -1:
				reply = Base(obj).get_error_message("You dont have permission to perform tasks.")
			else:
				reply = Base(obj).get_error_message()
		return reply
	
	def load_more(self, query):
		class_name = Helper().get_doctype_name_from_bot_name(query.bot_name)
		print class_name
		if class_name != 'Error':
			fields = Helper().get_doctype_fields_from_bot_name(query.bot_name)
			page_count = str(query.page_count)
			start = (int(page_count) - 1) * 20
			end = start + 20
			email = str(query.email)
			items = Helper().get_list(class_name, fields, start, end, {"owner":email})
			
			return globals()[class_name]().map_list(items)
		
		return []




class Base(object):

	def __init__(self, obj):
		self.obj = obj
		self.utils = Utils()
		self.query = Query(obj.bot_name)
		self.helper = Helper()

	def get_error_message(self, msg="Something went wrong, Please try in a little bit."):
		obj = self.obj
		obj.text = msg
		obj.created_at = self.get_created_at()
		obj.action = self.prepare_action(None, None, None)
		obj.info = self.prepare_info(None, None, None)
		obj.list_items = self.prepare_list_items(None, [])
		return self.utils.create_bot_message_object(obj.room, obj)

	def get_action_by_text(self, text):
		return self.query.get_action_from_text(text)

	def get_list(self, doctype, fields, filters):
		return self.helper.get_list(doctype, fields, 0, 3, filters)

	def get_created_at(self):
		return self.utils.get_date(str(datetime.datetime.now()))

	def prepare_action(self, x, y, z):
		return {
			"base_action": x,
			"action_on_button_click": y,
			"action_on_list_item_click": z
		}

	def prepare_info(self, x, y, z):
		return {
			"button_text": x,
			"is_interactive_chat": y,
			"is_interactive_list": z
		}

	def prepare_list_items(self, x, y):
		return {
			"action_on_internal_item_click": x,
			"items": y
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
		print method
		if method == 'error':
			return self.get_error_message("Something went wrong, please try a diffrent query")
		else:
			return getattr(self, method)()

	def prepare_obj(self, obj, method_name, base_action, action_on_button_click,
					action_on_list_item_click, button_text, is_interactive_chat,
					is_intereactive_list, action_on_internal_item_click, items):
		obj.text = self.messages.get(method_name)
		obj.created_at = self.get_created_at()
		obj.action = self.prepare_action(base_action, action_on_button_click, action_on_list_item_click)
		obj.info = self.prepare_info(button_text, is_interactive_chat, is_intereactive_list)
		obj.list_items = self.prepare_list_items(action_on_internal_item_click, items)
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
		obj = self.prepare_obj(self.obj, 'create', 'create_',
							   None, None, None, False, False, None, [])
		reply = self.utils.create_bot_message_object(obj.room, obj)
		print reply
		return reply

	def update(self):
		items = self.get_list(self.doctype, self.fields,
							  filters={"owner": self.obj.user_id})
		mapped_items = self.map_list(items)
		obj = self.prepare_obj(self.obj, 'update', 'update_',
								'load_more', 'update_', 'load more', False, 
								True, 'update_', mapped_items)
		reply = self.utils.create_bot_message_object(obj.room, obj)
		print reply
		return reply

	def delete(self):
		items = self.get_list(self.doctype, self.fields,
							  filters={"owner": self.obj.user_id})
		mapped_items = self.map_list(items)
		obj = self.prepare_obj(self.obj, 'delete', 'delete_',
								'load_more', 'delete_', 'load more', False, 
								True, 'delete_', mapped_items)
		reply = self.utils.create_bot_message_object(obj.room, obj)
		print reply
		return reply

	def get(self):
		items = self.get_list(self.doctype, self.fields,
							  filters={"owner": self.obj.user_id})
		mapped_items = self.map_list(items)
		obj = self.prepare_obj(self.obj, 'get', None,
								'load_more', 'get_item_info', 'load more', False, 
								True, 'get_item_info', mapped_items)
		reply = self.utils.create_bot_message_object(obj.room, obj)
		print reply
		return reply

	def create_(self):
		data =  globals()[self.doctype]().create_(self.doctype, self.obj)
		if data.is_success:
			items = self.get_list(self.doctype, self.fields, data.filters)
			mapped_items = self.map_list(items)
			obj = self.prepare_obj(self.obj, 'create_', None,
									'get_item_info', None, 'view info', True, 
									False, None, mapped_items)
			reply = self.utils.create_bot_message_object(obj.room, obj)
		else:
			reply = self.get_error_message()
		print reply
		return reply

	def update_(self):
		data =  globals()[self.doctype]().update_(self.doctype, self.obj)
		if data.is_success:
			items = self.get_list(self.doctype, self.fields, data.filters)
			mapped_items = self.map_list(items)
			obj = self.prepare_obj(self.obj, 'update_', None,
								'get_item_info', None, 'view info', True, 
								False, None, mapped_items)
			reply = self.utils.create_bot_message_object(obj.room, obj)
		else:
			reply = self.get_error_message()
		print reply
		return reply

	def delete_(self):
		filters = {"name": self.obj.item_id, "owner": self.obj.user_id}
		try:
			items = self.get_list(self.doctype, self.fields, filters)
			if len(items) > 0:
				frappe.delete_doc(self.doctype, self.obj.item_id)
				frappe.db.commit()
				mapped_items = self.map_list(items)
				obj = self.prepare_obj(self.obj, 'delete_', None,
								'get_item_info', None, 'view info', True, 
								False, None, mapped_items)
				reply = self.utils.create_bot_message_object(obj.room, obj)
			else:
				reply = self.get_error_message("Looks like item already deleted from database.")
		except Exception, e:
			print e
			reply = self.get_error_message()
		print reply
		return reply


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
