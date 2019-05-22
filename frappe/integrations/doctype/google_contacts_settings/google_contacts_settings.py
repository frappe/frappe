# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

if frappe.conf.developer_mode:
	import os
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = 'https://www.googleapis.com/auth/contacts'
GET_REQUEST = 'https://people.googleapis.com/v1/people/me/connections'

class GoogleContactsSettings(Document):

	def sync(self):
		"""Get and Create Contact from Google People API"""
		frappe.has_permission('Google Contacts Settings', throw=True)
		headers = {
			"Authorization": "Bearer {0}".format(self.get_access_token())
		}

		contacts = requests.get('https://people.googleapis.com/v1/people/me/connections', headers=headers).json()
		print(contacts)

	def get_access_token(self):
		if not self.refresh_token:
			raise frappe.ValidationError(_("Google Contacts is not configured."))
		data = {
			'client_id': self.client_id,
			'client_secret': self.get_password(fieldname='client_secret',raise_exception=False),
			'scope': SCOPES
		}
		try:
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
		except requests.exceptions.HTTPError:
			frappe.throw(_("Something went wrong during the token generation. Please request again an authorization code."))
		return r.get('access_token')

@frappe.whitelist()
def sync():
	try:
		google_contacts_settings = frappe.get_doc('Google Contacts Settings')
		if google_contacts_settings.enable == 1:
			google_contacts_settings.sync()
	except Exception:
		frappe.log_error(frappe.get_traceback())