from __future__ import unicode_literals
import frappe
from frappe.core.doctype.user.user import create_contact

def execute():
	""" Create Contact for each User if not present """
	frappe.reload_doc('contacts', 'doctype', 'contact')

	users = frappe.get_all('User', filters={"name": ('not in', 'Administrator, Guest')}, fields=["*"])
	for user in users:
		create_contact(user)
