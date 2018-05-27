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
		if re.findall("[{0}]+".format(special_characters), user.full_name):
			continue
		create_contact(user)
