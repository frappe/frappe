from __future__ import unicode_literals
import frappe
import os
import json
from frappe import conf
from frappe.utils.kickapp.reply import Reply

@frappe.whitelist()
def get_dev_port():
	return conf.get("developer_mode"), conf.get('socketio_port')

@frappe.whitelist()
def get_all_users(email):
	return get_response_from_method_name("get_all_users", email)

@frappe.whitelist()
def set_users_in_room(obj):
	obj = frappe._dict(json.loads(obj))
	return get_response_from_method_name("set_users_in_room", obj)

@frappe.whitelist()
def get_users_in_room(room):
	return get_response_from_method_name("get_users_in_room", room)

@frappe.whitelist()
def load_more(query):
	query = frappe._dict(json.loads(query))
	return get_response_from_method_name("load_more", query)

@frappe.whitelist()
def remove_user_from_group(obj):
	obj = frappe._dict(json.loads(obj))
	return get_response_from_method_name("remove_user_from_group", obj)

@frappe.whitelist()
def get_message_for_first_time(obj):
	obj = frappe._dict(json.loads(obj))
	get_response_from_method_name("get_message_for_first_time", obj, False)

@frappe.whitelist()
def send_message_and_get_reply(query):
	query = frappe._dict(json.loads(query))
	get_response_from_method_name("send_message_and_get_reply", query, False)

@frappe.whitelist()
def get_all_bots():
	return getattr(Reply(), 'get_all_bots')()

@frappe.whitelist()
def get_user_by_email(email):
	return get_response_from_method_name("get_user_by_email", email)

@frappe.whitelist()
def get_meta():
	return frappe.get_meta('ToDo')

def get_response_from_method_name(method_name, obj, is_return = True):
	if is_return:
		return getattr(Reply(), method_name)(obj)
	getattr(Reply(), method_name)(obj)
