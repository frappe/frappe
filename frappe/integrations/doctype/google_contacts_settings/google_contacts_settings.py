# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

if frappe.conf.developer_mode:
	import os
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = 'https://www.googleapis.com/auth/calendar'
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"

class GoogleContactsSettings(Document):

	def get_access_token(self):
		if not self.refresh_token:
			raise frappe.ValidationError(_("GCalendar is not configured."))
		data = {
			'client_id': self.client_id,
			'client_secret': self.get_password(fieldname='client_secret',raise_exception=False),
			'refresh_token': self.get_password(fieldname='refresh_token',raise_exception=False),
			'grant_type': "refresh_token",
			'scope': SCOPES
		}
		try:
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
		except requests.exceptions.HTTPError:
			frappe.throw(_("Something went wrong during the token generation. Please request again an authorization code."))
		return r.get('access_token')
