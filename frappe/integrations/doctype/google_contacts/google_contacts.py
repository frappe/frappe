# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_request_site_address

REQUEST = 'https://people.googleapis.com/v1/people/me/connections'
PARAMS = {'personFields': 'names,emailAddresses'}

class GoogleContacts(Document):

	def validate(self):
		if not frappe.db.exists("Google Contacts", {"user", self.user}):
			frappe.throw(_("Google Contacts Integration for User already exists."))

@frappe.whitelist()
def sync(contact=None):
	filters = {"enable": 1}

	if contact:
		filters.update({"name": contact})

	access_token = frappe.get_doc("Google Contacts Settings").get_access_token()
	google_contacts = frappe.get_list("Google Contacts", filters=filters)

	for google_contact in google_contacts:
		doc = frappe.get_doc("Google Contacts", google_contact.name)

		headers = {'Authorization': 'Bearer {}'.format(access_token)}

		try:
			r = requests.get(REQUEST, headers=headers, params=PARAMS)
		except Exception as e:
			frappe.throw(e.message)

		try:
			r = r.json()
		except Exception as e:
			# if request doesn't return json show HTML ask permissions or to identify the error on google side
			frappe.throw(e)

		connections = r.get('connections')
		contacts_updated = 0

		if connections:
			for idx, connection in enumerate(connections):
				for name in connection.get('names'):
					if contact:
						show_progress(len(connections), "Google Contacts", idx, name.get('displayName'))
					for email in connection.get('emailAddresses'):
						if not frappe.db.exists("Contact", {"email_id": email.get('value')}):
							contacts_updated += 1
							frappe.get_doc({
								"doctype": "Contact",
								"first_name": name.get('givenName'),
								"last_name": name.get('familyName'),
								"email_id": email.get('value'),
								"source": "Google Contacts"
							}).insert(ignore_permissions=True)

			return "{} Google Contacts synced.".format(contacts_updated) if contacts_updated > 0 else "No new Google Contacts synced."

		return "No Google Contacts present to sync." # If no Google Contacts to sync

def show_progress(length, message, i, description):
	if length > 5:
		frappe.publish_progress(
			float(i) * 100 / length,
			title = message,
			description = description
		)
