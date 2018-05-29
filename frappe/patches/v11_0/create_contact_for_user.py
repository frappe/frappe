from __future__ import unicode_literals
import frappe
from frappe.core.doctype.user.user import create_contact
import re

def execute():
	""" Create Contact for each User if not present """
	frappe.reload_doc('contacts', 'doctype', 'contact')

	users = frappe.get_all('User', filters={"name": ('not in', 'Administrator, Guest')}, fields=["*"])
	special_characters = "<>"
	for user in users:
		user.first_name = re.sub("[{0}]+".format(special_characters), '', str(user.first_name))
		user.last_name  = re.sub("[{0}]+".format(special_characters), '', str(user.last_name))
		create_contact(user)
