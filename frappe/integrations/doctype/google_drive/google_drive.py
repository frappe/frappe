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
from frappe.utils.background_jobs import enqueue
from six.moves.urllib.parse import quote
from apiclient.http import MediaFileUpload
from frappe.utils import get_backups_path, get_bench_path
from frappe.utils.backups import new_backup
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size


SCOPES = "https://www.googleapis.com/auth/drive"

class GoogleDrive(Document):

	def validate(self):
		doc_before_save = self.get_doc_before_save()
		if doc_before_save and doc_before_save.backup_folder_name != self.backup_folder_name:
			self.backup_folder_id = ''

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
def authorize_access(reauthorize=None):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_drive = frappe.get_doc("Google Drive")

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_drive.google_drive.google_callback"

	if not google_drive.authorization_code or reauthorize:
		if reauthorize:
			frappe.db.set_value("Google Drive", None, "backup_folder_id", "")
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

	authorize_access()

def get_google_drive_object():
	"""
		Returns an object of Google Drive.
	"""
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Drive")

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.get_password(fieldname="refresh_token", raise_exception=False),
		"token_uri": get_auth_url(),
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes": "https://www.googleapis.com/auth/drive/v3"
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_drive = googleapiclient.discovery.build("drive", "v3", credentials=credentials)

	return google_drive, account

def check_for_folder_in_google_drive():
	"""Checks if folder exists in Google Drive else create it."""
	def _create_folder_in_google_drive(google_drive, account):
		file_metadata = {
			"name": account.backup_folder_name,
			"mimeType": "application/vnd.google-apps.folder"
		}

		try:
			folder = google_drive.files().create(body=file_metadata, fields="id").execute()
			frappe.db.set_value("Google Drive", None, "backup_folder_id", folder.get("id"))
			frappe.db.commit()
		except HttpError as e:
			frappe.throw(_("Google Drive - Could not create folder in Google Drive - Error Code {0}").format(e))

	google_drive, account = get_google_drive_object()

	if account.backup_folder_id:
		return

	backup_folder_exists = False

	try:
		google_drive_folders = google_drive.files().list(q="mimeType='application/vnd.google-apps.folder'").execute()
	except HttpError as e:
		frappe.throw(_("Google Drive - Could not find folder in Google Drive - Error Code {0}").format(e))

	for f in google_drive_folders.get("files"):
		if f.get("name") == account.backup_folder_name:
			frappe.db.set_value("Google Drive", None, "backup_folder_id", f.get("id"))
			frappe.db.commit()
			backup_folder_exists = True
			break

	if not backup_folder_exists:
		_create_folder_in_google_drive(google_drive, account)

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to Google Drive"""
	enqueue("frappe.integrations.doctype.google_drive.google_drive.upload_system_backup_to_google_drive", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))

def upload_system_backup_to_google_drive():
	"""
		Upload system backup to Google Drive
	"""
	# Get Google Drive Object
	google_drive, account = get_google_drive_object()

	# Check if folder exists in Google Drive
	check_for_folder_in_google_drive()
	account.load_from_db()

	validate_file_size()
	if frappe.flags.create_new_backup:
		set_progress(1, "Backing up Data.")
		backup = new_backup()

		fileurl_backup = os.path.basename(backup.backup_path_db)
		fileurl_public_files = os.path.basename(backup.backup_path_files)
		fileurl_private_files = os.path.basename(backup.backup_path_private_files)
	else:
		fileurl_backup, fileurl_public_files, fileurl_private_files = get_latest_backup_file(with_files=True)

	for fileurl in [fileurl_backup, fileurl_public_files, fileurl_private_files]:
		file_metadata = {
			"name": fileurl,
			"parents": [account.backup_folder_id]
		}

		try:
			media = MediaFileUpload(get_absolute_path(filename=fileurl), mimetype="application/gzip", resumable=True)
		except IOError as e:
			frappe.throw(_("Google Drive - Could not locate locate - {0}").format(e))

		try:
			set_progress(2, "Uploading backup to Google Drive.")
			google_drive.files().create(body=file_metadata, media_body=media, fields="id").execute()
		except HttpError as e:
			send_email(False, "Google Drive", "Google Drive", "email", error_status=e)

	set_progress(3, "Uploading successful.")
	frappe.db.set_value("Google Drive", None, "last_backup_on", frappe.utils.now_datetime())
	send_email(True, "Google Drive", "Google Drive", "email")
	return _("Google Drive Backup Successful.")

def daily_backup():
	if frappe.db.get_single_value("Google Drive", "frequency") == "Daily":
		upload_system_backup_to_google_drive()

def weekly_backup():
	if frappe.db.get_single_value("Google Drive", "frequency") == "Weekly":
		upload_system_backup_to_google_drive()

def get_absolute_path(filename):
	file_path = os.path.join(get_backups_path()[2:], filename)
	return "{0}/sites/{1}".format(get_bench_path(), file_path)

def set_progress(progress, message):
	frappe.publish_realtime("upload_to_google_drive", dict(progress=progress, total=3, message=message), user=frappe.session.user)
