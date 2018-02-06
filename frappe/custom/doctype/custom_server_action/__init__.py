
# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe, json
from frappe import _
from frappe.utils.safe_eval import safe_eval, test_python_expr
from frappe.utils import nowdate, parse_val
from six import string_types
#from custom_server_action import evaluate_custom_server_action


def run_custom_server_action(doc, method):
	'''Run email alerts for this method'''
	if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
		return

	if doc.flags.custom_server_action_executed is None:
		doc.flags.custom_server_action_executed = []

	if doc.flags.custom_server_actions is None:
		custom_server_actions = frappe.cache().hget('custom_server_action', doc.doctype)
		if custom_server_actions is None:			
			server_actions = frappe.get_all('Custom Server Action',
							filters={'enabled': 1, 'document_type': doc.doctype})
			#retrieve all fields include child table
			custom_server_actions=[frappe.get_doc("Custom Server Action", sa.name) for sa in server_actions] 
			frappe.cache().hset('custom_server_action', doc.doctype, custom_server_actions)
		doc.flags.custom_server_actions = custom_server_actions

	if not doc.flags.custom_server_actions:
		return

	def _evaluate_custom_server_action(custom_server_action):
		if not custom_server_action.name in doc.flags.custom_server_action_executed:
			evaluate_custom_server_action(doc, custom_server_action, custom_server_action.event)
			doc.flags.custom_server_action_executed.append(custom_server_action.name)

	event_map = {
		"on_update": "Save",
		"after_insert": "New",
		"on_submit": "Submit",
		"on_cancel": "Cancel"
	}

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_map['validate'] = 'Value Change'
		event_map['before_change'] = 'Value Change'
		event_map['before_update_after_submit'] = 'Value Change'

	for custom_server_action in doc.flags.custom_server_actions:
		event = event_map.get(method, None)
		if event and custom_server_action.event == event:
			_evaluate_custom_server_action(custom_server_action)
		elif custom_server_action.event=='Method' and method == custom_server_action.method:
			_evaluate_custom_server_action(custom_server_action)

def evaluate_custom_server_action(doc, server_action, event):	
	#server_action = frappe.get_doc("Custom Server Action", server_action)
	context = get_context(doc)
	if server_action.condition:
		if not frappe.safe_eval(server_action.condition, None, context):
			return

	if event == "Value Change" and not doc.is_new():
		try:
			db_value = frappe.db.get_value(doc.doctype, doc.name, server_action.value_changed)
		except frappe.DatabaseOperationalError as e:
			if e.args[0] == 1054:
				server_action.db_set('enabled', 0)
				frappe.log_error('Custom Server Action {0} has been disabled due to missing field'.format(server_action.name))
				return

		db_value = parse_val(db_value)
		if (doc.get(server_action.value_changed) == db_value) or (not db_value and not doc.get(server_action.value_changed)):
			return  # value not changed

	if event != "Value Change" and not doc.is_new():
		# reload the doc for the latest values & comments,
		# except for validate type event.
		doc = frappe.get_doc(doc.doctype, doc.name)

	send(server_action, doc)

def send(server_action, doc):
	'''send Custom Server Action'''
	eval_context = get_context(doc)
	if server_action.document_type != server_action.target_document_type:
		if isinstance(doc.get(server_action.link_field), string_types):
			update_doc = frappe.get_doc(server_action.target_document_type, doc.get(server_action.link_field))
		else:
			update_doc = doc.get(server_action.link_field)
		eval_context.update({'update_doc': update_doc})

	field_dict = {}
	
	for line in server_action.value_mapping:
		expr = line.value if line.type == "Value" else safe_eval(line.value, {}, eval_context)
		field_dict.update({line.doc_field: expr})
	if server_action.action_type == "Update Record":
		if update_doc:
			doc = update_doc  # update_doc to be changed
		frappe.db.set_value(doc.doctype, doc.name, field_dict, None, update_modified=False)
		for key, value in field_dict.items():
			doc.set(key, value)
	elif server_action.action_type == "Create New Record":
		field_dict.update({'doctype': server_action.target_document_type})
		frappe.get_doc(field_dict).insert()
	elif server_action.action_type == "Execute Python Code":
		safe_eval(server_action.code, eval_context, mode='exec')
		# exception raised via frappe.throw in safe_eval can not be handled by outer app.py, throw here instead
		validation_msg = frappe.local.form_dict.get('validation_msg')
		if validation_msg:
			frappe.local.form_dict.pop('validation_msg') 
			frappe.throw(validation_msg)

@frappe.whitelist()
def run_custom_server_action_by_js(*args,**kwargs):
	server_action_name = kwargs.get('server_action_name') or frappe.local.form_dict.get('server_action_name')
	if not server_action_name:
		return
	else:
		server_action_doc = frappe.get_doc('Custom Server Action', server_action_name)		
	if not server_action_doc or (not server_action_doc.enabled or server_action_doc.action_type != 'Execute Python Code'):
		frappe.respond_as_web_page(title='Invalid Custom Server Action Method', html='Method not found',
			                    indicator_color='red', http_status_code=404)
		return
	else:
		eval_context = get_context()
		try:
			safe_eval(server_action_doc.code, eval_context, mode='exec')
		except Exception as e:
			frappe.log_error(message=frappe.get_traceback() +  str(e), title ='custom server action runtime error')
			server_action_doc.db_set('enabled', 0)
		data = frappe.local.form_dict.get('custom_server_action_out','')
		if data:
			frappe.local.form_dict.pop('custom_server_action_out') # remove as this is global shared			
			return data

def msgprint(msg):
	frappe.local.form_dict.update({'validation_msg':msg)

def get_context(doc=None):
	return {"doc": doc, "frappe": frappe, "nowdate": nowdate, 
		"frappe.utils": frappe.utils, '_': _, 'json' : json, 'msgprint': msgprint}

