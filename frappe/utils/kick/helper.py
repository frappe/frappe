from __future__ import unicode_literals
import frappe, re
import frappe
import json
import datetime


def get_user_info(email):
	return frappe.get_list('User', ["email", "full_name", "last_active"],
			filters={"email":email})[0]

def get_all_communication(user_email):
	return frappe.get_list('Communication', 
		["name", "subject", "creation", "content", "sender", "recipients", 
		"reference_name", "reference_doctype", "reference_owner", "status", 
		"sent_or_received"], 
		{"user": user_email, "communication_type" :"Communication"})
	
def get_created_at(created_at):
	#server side its created_on and client side it's created_at 
	created_on = str(created_at)
	return created_on.split('.')[0]


