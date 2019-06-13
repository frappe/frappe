# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_request_site_address

SCOPES = 'https://www.googleapis.com/auth/contacts'
REQUEST = 'https://people.googleapis.com/v1/people/me/connections'
PARAMS = {'personFields': 'names,emailAddresses'}

class GoogleContacts(Document):

	def validate(self):
		if frappe.db.exists("Google Contacts", {"user", self.user}):
			frappe.throw(_("Google Contacts Integration for User already exists."))

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Contacts Integration is disabled."))

		if not self.refresh_token:
			raise frappe.ValidationError(_("Enable Google Contacts access."))

		data = {
			'client_id': google_settings.client_id,
			'client_secret': google_settings.client_secret, #get_password(fieldname='client_secret', raise_exception=False),
			'refresh_token': self.refresh_token, #get_password(fieldname='refresh_token', raise_exception=False),
			'grant_type': "refresh_token",
			'scope': SCOPES
		}

		try:
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
		except requests.exceptions.HTTPError:
			frappe.throw(_("Something went wrong during the token generation. Please request again an authorization code."))

		return r.get('access_token')

@frappe.whitelist()
def authenticate_access(g_contact):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_contact = frappe.get_doc("Google Contacts", g_contact)

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_contacts.google_contacts.google_callback"

	if not google_contact.authorization_code:
		frappe.flags.google_contact = google_contact.name
		return google_callback(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				'code': google_contact.authorization_code,
				'client_id': google_settings.client_id,
				'client_secret': google_settings.client_secret, #get_password(fieldname='client_secret', raise_exception=False),
				'redirect_uri': redirect_uri,
				'grant_type': 'authorization_code'
			}
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()

			if 'refresh_token' in r:
				frappe.db.set_value("Google Contacts", google_contact.name, "refresh_token", r.get("refresh_token"))

			frappe.db.commit()
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/Google%20Contacts/{}".format(google_contact.name)

			frappe.msgprint(_("Google Contacts has been configured."))
		except Exception as e:
			frappe.throw(e)

@frappe.whitelist()
def google_callback(client_id=None, redirect_uri=None, code=None):
	"""
		Authorization code is sent to callback as per the API configuration
	"""
	if code is None:
		return {
			'url': 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}'.format(client_id, SCOPES, redirect_uri)
		}
	else:
		frappe.db.set_value("Google Contacts", frappe.flags.google_contact, "authorization_code", code)
		authenticate_access(frappe.flags.google_contact)

# @frappe.whitelist()
# def sync(g_contact=None):
# 	filters = {"enable": 1}

# 	if contact:
# 		filters.update({"name": contact})

# 	access_token = frappe.get_doc("Google Contacts").get_access_token()
# 	google_contacts = frappe.get_list("Google Contacts", filters=filters)

# 	for google_contact in google_contacts:
# 		doc = frappe.get_doc("Google Contacts", google_contact.name)

# 		headers = {'Authorization': 'Bearer {}'.format(access_token)}

# 		try:
# 			r = requests.get(REQUEST, headers=headers, params=PARAMS)
# 		except Exception as e:
# 			frappe.throw(e.message)

# 		try:
# 			r = r.json()
# 		except Exception as e:
# 			# if request doesn't return json show HTML ask permissions or to identify the error on google side
# 			frappe.throw(e)

# 		connections = r.get('connections')
# 		contacts_updated = 0

# 		if connections:
# 			for idx, connection in enumerate(connections):
# 				for name in connection.get('names'):
# 					if contact:
# 						show_progress(len(connections), "Google Contacts", idx, name.get('displayName'))
# 					for email in connection.get('emailAddresses'):
# 						if not frappe.db.exists("Contact", {"email_id": email.get('value')}):
# 							contacts_updated += 1
# 							frappe.get_doc({
# 								"doctype": "Contact",
# 								"first_name": name.get('givenName'),
# 								"last_name": name.get('familyName'),
# 								"email_id": email.get('value'),
# 								"source": "Google Contacts"
# 							}).insert(ignore_permissions=True)

# 			return "{} Google Contacts synced.".format(contacts_updated) if contacts_updated > 0 else "No new Google Contacts synced."

# 		return "No Google Contacts present to sync." # If no Google Contacts to sync

# def show_progress(length, message, i, description):
# 	if length > 5:
# 		frappe.publish_progress(
# 			float(i) * 100 / length,
# 			title = message,
# 			description = description
# 		)
