from __future__ import unicode_literals
import frappe, re

action_mapper = {"create":"create_doc", "update":"update_doc",
	"delete":"delete_doc", "show":"get_doc", "basic":"basic_replies", 
	"count":"count_docs", "default":"error_message"}

actions = frappe._dict({d.upper():d.lower() for d in action_mapper.keys()}) 

def get_method_name_from_action(action):
	return action_mapper.get(action.lower(), None)



