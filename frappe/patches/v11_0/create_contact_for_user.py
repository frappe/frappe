from __future__ import unicode_literals
import frappe
from frappe.core.doctype.user.user import create_contact
import re

def execute():
	""" Create Contact for each User if not present """
	frappe.reload_doc('contacts', 'doctype', 'contact')

	users = frappe.get_all('User', filters={"name": ('not in', 'Administrator, Guest')}, fields=["*"])
	for user in users:
		if user.first_name:
			user.first_name = re.sub("[<>]+", '', frappe.safe_decode(user.first_name))
		if user.last_name:
			user.last_name  = re.sub("[<>]+", '', frappe.safe_decode(user.last_name))
		create_contact(user, ignore_links=True, ignore_mandatory=True)
