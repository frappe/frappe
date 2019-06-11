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

class GoogleContactsSettings(Document):

	def get_access_token(self):
		if not self.refresh_token:
			raise frappe.ValidationError(_("Google Contacts is not configured."))

		data = {
			'client_id': self.client_id,
			'client_secret': self.client_secret, #get_password(fieldname='client_secret', raise_exception=False),
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
def google_callback(code=None):
	doc = frappe.get_doc("Google Contacts Settings")

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_contacts_settings.google_contacts_settings.google_callback"

	if code is None:
		return {
			'url': 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}'.format(doc.client_id, SCOPES, redirect_uri)
		}
	else:
		try:
			data = {
				'code': code,
				'client_id': doc.client_id,
				'client_secret': doc.client_secret, #get_password(fieldname='client_secret', raise_exception=False),
				'redirect_uri': redirect_uri,
				'grant_type': 'authorization_code'
			}
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()

			frappe.db.set_value("Google Contacts Settings", None, "authorization_code", code)

			if 'refresh_token' in r:
				frappe.db.set_value("Google Contacts Settings", None, "refresh_token", r.get("refresh_token"))

			frappe.db.commit()
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/Google%20Contacts"
			return
		except Exception as e:
			frappe.throw(e.message)
