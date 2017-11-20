from __future__ import unicode_literals
import frappe
from frappe.utils.oauth import login_via_oauth2

@frappe.whitelist(allow_guest=True)
def login_via_github(code, state):
	login_via_oauth2("github", code, state)