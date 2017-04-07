from __future__ import unicode_literals
import frappe, re
from random import randint

action_mapper = {"create":"create_doc", "update":"update_doc",
	"delete":"delete_doc", "show":"get_doc", "basic":"basic_replies", 
	"count":"count_docs", "default":"error_message"}

actions = frappe._dict({d.upper():d.lower() for d in action_mapper.keys()}) 

stories = {"1":"he bro", "2":"he bro", "3":"he bro", "4":"he bro"}

def get_method_name_from_action(action):
	return action_mapper.get(action.lower(), None)

def get_random_story():
	return stories.get(randint(1,4), 'This is not a story')




