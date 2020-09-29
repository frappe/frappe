from __future__ import unicode_literals
import frappe
from frappe.core.doctype.user.user import create_contact
import re

def execute():
	""" Create Contact for each User if not present """
	frappe.reload_doc('integrations', 'doctype', 'google_contacts')
	frappe.reload_doc('contacts', 'doctype', 'contact')
	frappe.reload_doc('core', 'doctype', 'dynamic_link')
	frappe.reload_doc('communication', 'doctype', 'call_log')

	contact_meta = frappe.get_meta("Contact")
	if contact_meta.has_field("phone_nos") and contact_meta.has_field("email_ids"):
		frappe.reload_doc('contacts', 'doctype', 'contact_phone')
		frappe.reload_doc('contacts', 'doctype', 'contact_email')

	users = frappe.get_all('User', filters={"name": ('not in', 'Administrator, Guest')}, fields=["*"])
	for user in users:
		if frappe.db.exists("Contact", {"email_id": user.email}) or frappe.db.exists("Contact Email", {"email_id": user.email}):
			continue
		if user.first_name:
			user.first_name = re.sub("[<>]+", '', frappe.safe_decode(user.first_name))
		if user.last_name:
			user.last_name  = re.sub("[<>]+", '', frappe.safe_decode(user.last_name))
		create_contact(user, ignore_links=True, ignore_mandatory=True)
