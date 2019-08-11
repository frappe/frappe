# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import googleapiclient.discovery
import google.oauth2.credentials

from frappe import _
from googleapiclient.errors import HttpError
from frappe.model.document import Document
from frappe.utils import get_request_site_address
from six.moves.urllib.parse import quote
from apiclient.http import MediaFileUpload
from frappe.utils.file_manager import save_file, get_file_url
from frappe.utils.print_format import download_pdf

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
	google_drive_object = googleapiclient.discovery.build("drive", "v3", credentials=credentials)

	return google_drive_object, account

def create_folder_in_google_drive(google_drive_object, account):
	"""
		Create a folder on Drive, returns the newely created folders ID
	"""
	file_metadata = {
		"name": account.folder_name,
		"mimeType": "application/vnd.google-apps.folder"
	}
	folder = google_drive_object.files().create(body=file_metadata, fields="id").execute()
	frappe.db.set_value("Google Drive", account.name, "folder_id", folder.get("id"))

@frappe.whitelist()
def upload_document_to_google_drive(doctype, docname, g_drive, format, letterhead):
	"""
		Uploads Document to Folder specified in Google Drive Doc.
	"""
	google_drive_object, account = get_google_drive_object(g_drive)

	if not account.folder_id:
		create_folder_in_google_drive(google_drive_object, account)
		account.load_from_db()

	download_pdf(doctype=doctype, name=docname, format=format, no_letterhead=letterhead)

	filename = frappe.local.response.filename.replace(".pdf", "-{0}.pdf".format(frappe.generate_hash(length=5)))
	filecontent = frappe.local.response.filecontent

	upload_file = save_file(filename, filecontent, doctype, docname)

	if not upload_file:
		frappe.throw(_("Could not upload pdf to Google Drive"))

	fileurl = upload_file.file_url or upload_file.file_name
	file_metadata = {
		"name": filename,
		"parents": [account.folder_id]
	}

	media = MediaFileUpload(get_absolute_path(fileurl), mimetype="application/pdf")

	try:
		file = google_drive_object.files().create(body=file_metadata, media_body=media, fields="id").execute()
	except HttpError as e:
		frappe.msgprint(_("Google Drive - Could not upload file - Error Code {0}").format(e.resp.status))

def get_absolute_path(filename):
	filename = filename.replace("/files/", "")
	file_path = frappe.utils.get_path("public", "files", filename).replace("./", "")

	return "{0}/sites/{1}".format(frappe.utils.get_bench_path(), file_path)