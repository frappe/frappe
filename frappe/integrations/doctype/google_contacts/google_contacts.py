# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_request_site_address
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url

SCOPES = "https://www.googleapis.com/auth/contacts"
REQUEST = "https://people.googleapis.com/v1/people/me/connections"
PARAMS = {"personFields": "names,emailAddresses,organizations,phoneNumbers"}

class GoogleContacts(Document):

	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Contacts Integration is disabled."))

		if not self.refresh_token:
			button_label = frappe.bold(_('Allow Google Contacts Access'))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
			"refresh_token": self.get_password(fieldname="refresh_token", raise_exception=False),
			"grant_type": "refresh_token",
			"scope": SCOPES
		}

		try:
			r = requests.post(get_auth_url(), data=data).json()
		except requests.exceptions.HTTPError:
			button_label = frappe.bold(_('Allow Google Contacts Access'))
			frappe.throw(_("Something went wrong during the token generation. Click on {0} to generate a new one.").format(button_label))

		return r.get("access_token")

@frappe.whitelist()
def authorize_access(g_contact, reauthorize=None):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_contact = frappe.get_doc("Google Contacts", g_contact)

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_contacts.google_contacts.google_callback"

	if not google_contact.authorization_code or reauthorize:
		frappe.cache().hset("google_contacts", "google_contact", google_contact.name)
		return google_callback(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				"code": google_contact.authorization_code,
				"client_id": google_settings.client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code"
			}
			r = requests.post(get_auth_url(), data=data).json()

			if "refresh_token" in r:
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
			"url": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}".format(client_id, SCOPES, redirect_uri)
		}
	else:
		google_contact = frappe.cache().hget("google_contacts", "google_contact")
		frappe.db.set_value("Google Contacts", google_contact, "authorization_code", code)
		frappe.db.commit()

		authorize_access(google_contact)

@frappe.whitelist()
def sync(g_contact=None):
	filters = {"enable": 1}

	if g_contact:
		filters.update({"name": g_contact})

	google_contacts = frappe.get_list("Google Contacts", filters=filters)

	for google_contact in google_contacts:
		doc = frappe.get_doc("Google Contacts", google_contact.name)
		access_token = doc.get_access_token()

		headers = {"Authorization": "Bearer {}".format(access_token)}

		try:
			r = requests.get(REQUEST, headers=headers, params=PARAMS)
		except Exception as e:
			frappe.throw(e)

		try:
			r = r.json()
		except Exception as e:
			# if request doesn't return json show HTML ask permissions or to identify the error on google side
			frappe.throw(e)

		connections = r.get("connections")
		contacts_updated = 0

		frappe.db.set_value("Google Contacts", doc.name, "last_sync_on", frappe.utils.now_datetime())

		if connections:
			for idx, connection in enumerate(connections):
				frappe.publish_realtime('import_google_contacts', dict(progress=idx+1, total=r.get("totalPeople")), user=frappe.session.user)

				for name in connection.get("names"):
					if name.get("metadata").get("primary"):
						contact = frappe.get_doc({
							"doctype": "Contact",
							"salutation": name.get("honorificPrefix") or "",
							"first_name": name.get("givenName") or "",
							"middle_name": name.get("middleName") or "",
							"last_name": name.get("familyName") or "",
							"designation": get_indexed_value(connection.get("organizations"), 0, "title"),
							"source": "Google Contacts",
							"google_contacts_description": get_indexed_value(connection.get("organizations"), 0, "name")
						})

						for email in connection.get("emailAddresses", []):
							contact.add_email(email_id=email.get("value"), is_primary=1 if email.get("primary") else 0)

						for phone in connection.get("phoneNumbers", []):
							contact.add_phone(phone=phone.get("value"), is_primary=1 if phone.get("primary") else 0)

						contact.insert(ignore_permissions=True)

			if g_contact:
				return _("{0} Google Contacts synced.").format(contacts_updated) if contacts_updated > 0 else _("No new Google Contacts synced.")

		if g_contact:
			return _("No Google Contacts present to sync.") # If no Google Contacts to sync

def get_indexed_value(d, index, key):
	if not d:
		return ""

	try:
		return d[index].get(key)
	except IndexError:
		return ""
