# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import googleapiclient.discovery
import google.oauth2.credentials
import os

from frappe import _
from googleapiclient.errors import HttpError
from frappe.model.document import Document
from frappe.utils import get_request_site_address
from six.moves.urllib.parse import quote
from apiclient.http import MediaFileUpload
from frappe.utils.file_manager import save_file
from frappe.utils.print_format import download_pdf
from frappe.utils import get_backups_path, get_files_path, get_bench_path
from frappe.utils.backups import new_backup
from frappe.utils import now
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url

SCOPES = "https://www.googleapis.com/auth/drive/v3"

class GoogleDrive(Document):

	def validate(self):
		if self.enable_system_backup:
			system_backup = frappe.db.exists("Google Drive", {"enable_system_backup": 1})
			if system_backup and not system_backup == self.name:
				frappe.throw(_("Google Drive System Backup can be enabled only for one account."))

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
			r = requests.post(get_auth_url(), data=data).json()
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
	google_drive = frappe.get_doc("Google Drive")

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_drive.google_drive.google_callback"

	if not google_drive.authorization_code or reauthorize:
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
			r = requests.post(get_auth_url(), data=data).json()

			if "refresh_token" in r:
				frappe.db.set_value("Google Drive", google_drive.name, "refresh_token", r.get("refresh_token"))
				frappe.db.commit()

			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/{0}".format(quote("Google Drive"))

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
	frappe.db.set_value("Google Drive", None, "authorization_code", code)
	frappe.db.commit()

	authorize_access(google_drive)

def get_google_drive_object(g_drive):
	"""
		Returns an object of Google Drive.
	"""
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Drive", g_drive)

	if not account.backup_folder_id:
		frappe.throw(_("Folder {0} not created in Google Drive.").format(account.backup_folder_name))

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.get_password(fieldname="refresh_token", raise_exception=False),
		"token_uri": get_auth_url(),
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes": SCOPES
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_drive = googleapiclient.discovery.build("drive", "v3", credentials=credentials)

	return google_drive, account

@frappe.whitelist()
def create_folder_in_google_drive(google_drive=None, account=None, g_drive=None):
	if g_drive:
		google_drive, account = get_google_drive_object(g_drive)

	file_metadata = {
		"name": account.backup_folder_name,
		"mimeType": "application/vnd.google-apps.folder"
	}
	try:
		folder = google_drive.files().create(body=file_metadata, fields="id").execute()
		frappe.db.set_value("Google Drive", None, "backup_folder_id", folder.get("id"))
	except HttpError as e:
		frappe.throw(_("Google Drive - Could not create folder in Google Drive - Error Code {0}").format(e))

	return "Folder created successfully in Google Drive."

def check_for_folder_in_google_drive(google_drive, account):
	"""
		Create a folder on Drive, returns the newely created folders ID
	"""
	if not account.backup_folder_id:
		create_folder_in_google_drive(google_drive, account)
		return

	try:
		google_drive.files().get(fileId=account.backup_folder_id, fields="id").execute()
	except HttpError as e:
		frappe.throw(_("Google Drive - Could not find folder in Google Drive - Error Code {0}.").format(e))

@frappe.whitelist()
def upload_system_backup_to_google_drive(g_drive):
	"""
		Upload system backup to Google Drive
	"""
	# Get Google Drive Object
	google_drive, account = get_google_drive_object(g_drive)

	# Check if folder exists in Google Drive
	check_for_folder_in_google_drive(google_drive, account)
	account.load_from_db()

	backup = new_backup(ignore_files=True)

	fileurl = os.path.basename(backup.backup_path_db)

	file_metadata = {
		"name": "Instance Backup-{0}".format(frappe.utils.now()),
		"parents": [account.backup_folder_id]
	}

	media = MediaFileUpload(get_absolute_path(fileurl, True), mimetype="application/gzip", resumable=True)

	try:
		google_drive.files().create(body=file_metadata, media_body=media, fields="id").execute()
		frappe.db.set_value("Google Drive", None, "last_backup_on", frappe.utils.now_datetime())
	except HttpError as e:
		frappe.msgprint(_("Google Drive - Could not upload backup - Error {0}").format(e))

	return _("Google Drive Backup Successful.")

def daily_backup():
	g_drive = frappe.db.exists("Google Drive", {"enable": 1, "enable_system_backup": 1, "frequency": "Daily"})
	if g_drive:
		upload_system_backup_to_google_drive(g_drive)

def weekly_backup():
	g_drive = frappe.db.exists("Google Drive", {"enable": 1, "enable_system_backup": 1, "frequency": "Weekly"})
	if g_drive:
		upload_system_backup_to_google_drive(g_drive)

def get_absolute_path(filename, backup=False):
	file_path = os.path.join(get_files_path()[2:], filename)

	if backup:
		file_path = os.path.join(get_backups_path()[2:], filename)

	return "{0}/sites/{1}".format(get_bench_path(), file_path)