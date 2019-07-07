# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

SCOPES = 'https://www.googleapis.com/auth/calendar'
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"

SCOPES = "https://www.googleapis.com/auth/contacts"
REQUEST = "https://people.googleapis.com/v1/people/me/connections"
PARAMS = {"personFields": "names,emailAddresses,organizations,phoneNumbers"}

class GoogleCalendar(Document):

	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Calendar Integration is disabled."))

		if not self.refresh_token:
			button_label = frappe.bold(_('Allow Google Calendar Access'))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
			"refresh_token": self.get_password(fieldname="refresh_token", raise_exception=False),
			"grant_type": "refresh_token",
			"scope": SCOPES
		}

		try:
			r = requests.post("https://www.googleapis.com/oauth2/v4/token", data=data).json()
		except requests.exceptions.HTTPError:
			button_label = frappe.bold(_('Allow Google Calendar Access'))
			frappe.throw(_("Something went wrong during the token generation. Click on {0} to generate a new one.").format(button_label))

		return r.get("access_token")

@frappe.whitelist()
def google_callback(code=None, state=None, account=None):
	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.google_callback"
	if account is not None:
		frappe.cache().hset("gcalendar_account","GCalendar Account", account)
	doc = frappe.get_doc("GCalendar Settings")
	if code is None:
		return {
			'url': 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}'.format(doc.client_id, SCOPES, redirect_uri)
			}
	else:
		try:
			account = frappe.get_doc("Google Calendar", frappe.cache().hget("gcalendar_account", "GCalendar Account"))
			data = {'code': code,
				'client_id': doc.client_id,
				'client_secret': doc.get_password(fieldname='client_secret',raise_exception=False),
				'redirect_uri': redirect_uri,
				'grant_type': 'authorization_code'}

			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
			frappe.db.set_value("GCalendar Account", account.name, "authorization_code", code)
			if 'access_token' in r:
				frappe.db.set_value("GCalendar Account", account.name, "session_token", r['access_token'])
			if 'refresh_token' in r:
				frappe.db.set_value("GCalendar Account", account.name, "refresh_token", r['refresh_token'])
			frappe.db.commit()
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/integrations/gcalendar-success.html"
			return
		except Exception as e:
			frappe.throw(e.message)

@frappe.whitelist()
def authorize_access(g_calendar, reauthorize=None):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_calendar = frappe.get_doc("Google Calendar", g_calendar)

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"

	if not google_calendar.authorization_code or reauthorize:
		frappe.cache().hset("google_calendar", "google_calendar", google_calendar.name)
		return google_callback(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				"code": google_calendar.authorization_code,
				"client_id": google_settings.client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code"
			}
			r = requests.post("https://www.googleapis.com/oauth2/v4/token", data=data).json()

			if "refresh_token" in r:
				frappe.db.set_value("Google Calendar", google_calendar.name, "refresh_token", r.get("refresh_token"))
				frappe.db.commit()

			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/Google%20Contacts/{}".format(google_calendar.name)

			frappe.msgprint(_("Google Calendar has been configured."))
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
		google_calendar = frappe.cache().hget("google_calendar", "google_calendar")
		frappe.db.set_value("Google Calendar", google_calendar, "authorization_code", code)
		frappe.db.commit()

		authorize_access(google_calendar)