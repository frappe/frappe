# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
from frappe.utils.oauth import login_via_oauth2, login_via_oauth2_id_token
import json

@frappe.whitelist(allow_guest=True)
def login_via_google(code, state):
	login_via_oauth2("google", code, state, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_github(code, state):
	login_via_oauth2("github", code, state)

@frappe.whitelist(allow_guest=True)
def login_via_facebook(code, state):
	login_via_oauth2("facebook", code, state, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_frappe(code, state):
	login_via_oauth2("frappe", code, state, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_office365(code, state):
	login_via_oauth2_id_token("office_365", code, state, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_salesforce(code, state):
	login_via_oauth2("salesforce", code, state, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_fairlogin(code, state):
	login_via_oauth2("fairlogin", code, state, decoder=json.loads)
