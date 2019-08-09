# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import googleapiclient.discovery
import google.oauth2.credentials

from frappe import _
from frappe.model.document import Document
from frappe.utils import get_request_site_address
from six.moves.urllib.parse import quote
from apiclient.http import MediaFileUpload

SCOPES = "https://www.googleapis.com/auth/drive"

class GoogleDrive(Document):

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Integration is disabled."))

		if not self.refresh_token:
			button_label = frappe.bold(_("Allow Google Drive Access"))
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
			button_label = frappe.bold(_("Allow Google Drive Access"))
			frappe.throw(_("Something went wrong during the token generation. Click on {0} to generate a new one.").format(button_label))

		return r.get("access_token")

@frappe.whitelist()
def authorize_access(g_drive, reauthorize=None):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_drive = frappe.get_doc("Google Drive", g_drive)

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_drive.google_drive.google_callback"

	if not google_drive.authorization_code or reauthorize:
		frappe.cache().hset("google_drive", "google_drive", google_drive.name)
		return get_authentication_url(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				"code": google_drive.authorization_code,
				"client_id": google_settings.client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code"
			}
			r = requests.post("https://www.googleapis.com/oauth2/v4/token", data=data).json()

			if "refresh_token" in r:
				frappe.db.set_value("Google Drive", google_drive.name, "refresh_token", r.get("refresh_token"))
				frappe.db.commit()

			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/{0}/{1}".format(quote("Google Drive"), quote(google_drive.name))

			frappe.msgprint(_("Google Drive has been configured."))
		except Exception as e:
			frappe.throw(e)

def get_authentication_url(client_id, redirect_uri):
	return {
		"url": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}".format(client_id, SCOPES, redirect_uri)
	}

@frappe.whitelist()
def google_callback(code=None):
	"""
		Authorization code is sent to callback as per the API configuration
	"""
	google_drive = frappe.cache().hget("google_drive", "google_drive")
	frappe.db.set_value("Google Drive", google_drive, "authorization_code", code)
	frappe.db.commit()

	authorize_access(google_drive)

def get_google_drive_object(g_drive):
	"""
		Returns an object of Google Drive.
	"""
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Drive", g_drive)

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.get_password(fieldname="refresh_token", raise_exception=False),
		"token_uri": "https://www.googleapis.com/oauth2/v4/token",
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes": "https://www.googleapis.com/auth/drive/v3"
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_drive = googleapiclient.discovery.build("drive", "v3", credentials=credentials)

	return google_calendar

@frappe.whitelist()
def upload_document(doctype, docname, g_drive):
	from frappe.utils.print_format import download_pdf

	google_drive = get_google_drive_object(g_drive)
	download_pdf(doctype=doctype, docname=docname, format="pdf")
	file_metadata = {"name": frappe.local.response.filename}
	media = MediaFileUpload(frappe.local.response.filename, mimetype="application/pdf")

	file = google_drive.files().create(body=file_metadata, media_body=media, fields='id').execute()


	# frappe.local.response.filecontent
