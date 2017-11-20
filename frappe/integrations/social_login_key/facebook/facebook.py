from __future__ import unicode_literals
import frappe, json
from frappe.utils.oauth import login_via_oauth2

@frappe.whitelist(allow_guest=True)
def login_via_facebook(code, state):
	login_via_oauth2("facebook", code, state, decoder=json.loads)