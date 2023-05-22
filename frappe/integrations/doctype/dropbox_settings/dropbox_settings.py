# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import os
from urllib.parse import parse_qs, urlparse

import dropbox
from rq.timeouts import JobTimeoutException

import frappe
from frappe import _
from frappe.integrations.offsite_backup_utils import (
	get_chunk_site,
	get_latest_backup_file,
	send_email,
	validate_file_size,
)
from frappe.model.document import Document
from frappe.utils import cint, encode, get_backups_path, get_files_path, get_request_site_address
from frappe.utils.background_jobs import enqueue
from frappe.utils.backups import new_backup

ignore_list = [".DS_Store"]


class DropboxSettings(Document):
	def onload(self):
		if not self.app_access_key and frappe.conf.dropbox_access_key:
			self.set_onload("dropbox_setup_via_site_config", 1)

	def validate(self):
		if self.enabled and self.limit_no_of_backups and self.no_of_backups < 1:
			frappe.throw(_("Number of DB backups cannot be less than 1"))


@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to dropbox"""
	enqueue(
		"frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backup_to_dropbox",
		queue="long",
		timeout=1500,
	)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))


def take_backups_daily():
	take_backups_if("Daily")


def take_backups_weekly():
	take_backups_if("Weekly")


def take_backups_if(freq):
	if frappe.db.get_single_value("Dropbox Settings", "backup_frequency") == freq:
		take_backup_to_dropbox()


def take_backup_to_dropbox(retry_count=0, upload_db_backup=True):
	did_not_upload, error_log = [], []
	try:
		if cint(frappe.db.get_single_value("Dropbox Settings", "enabled")):
			validate_file_size()

			did_not_upload, error_log = backup_to_dropbox(upload_db_backup)
			if did_not_upload:
				raise Exception

			if cint(frappe.db.get_single_value("Dropbox Settings", "send_email_for_successful_backup")):
				send_email(True, "Dropbox", "Dropbox Settings", "send_notifications_to")
	except JobTimeoutException:
		if retry_count < 2:
			args = {
				"retry_count": retry_count + 1,
				"upload_db_backup": False,  # considering till worker timeout db backup is uploaded
			}
			enqueue(
				"frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backup_to_dropbox",
				queue="long",
				timeout=1500,
				**args,
			)
	except Exception:
		if isinstance(error_log, str):
			error_message = error_log + "\n" + frappe.get_traceback()
		else:
			file_and_error = [" - ".join(f) for f in zip(did_not_upload, error_log)]
			error_message = "\n".join(file_and_error) + "\n" + frappe.get_traceback()

		send_email(False, "Dropbox", "Dropbox Settings", "send_notifications_to", error_message)


def backup_to_dropbox(upload_db_backup=True):
	# upload database
	dropbox_settings = get_dropbox_settings()
	dropbox_client = get_dropbox_client(dropbox_settings)

	if upload_db_backup:
		if frappe.flags.create_new_backup:
			backup = new_backup(ignore_files=True)
			filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
			site_config = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_conf))
		else:
			filename, site_config = get_latest_backup_file()

		upload_file_to_dropbox(filename, "/database", dropbox_client)
		upload_file_to_dropbox(site_config, "/database", dropbox_client)

		# delete older databases
		if dropbox_settings["no_of_backups"]:
			delete_older_backups(dropbox_client, "/database", dropbox_settings["no_of_backups"])

	# upload files to files folder
	did_not_upload = []
	error_log = []

	if dropbox_settings["file_backup"]:
		upload_from_folder(get_files_path(), 0, "/files", dropbox_client, did_not_upload, error_log)
		upload_from_folder(
			get_files_path(is_private=1), 1, "/private/files", dropbox_client, did_not_upload, error_log
		)

	return did_not_upload, list(set(error_log))


def upload_from_folder(
	path, is_private, dropbox_folder, dropbox_client, did_not_upload, error_log
):
	if not os.path.exists(path):
		return

	if is_fresh_upload():
		response = get_uploaded_files_meta(dropbox_folder, dropbox_client)
	else:
		response = frappe._dict({"entries": []})

	path = str(path)

	for f in frappe.get_all(
		"File",
		filters={"is_folder": 0, "is_private": is_private, "uploaded_to_dropbox": 0},
		fields=["file_url", "name", "file_name"],
	):
		if not f.file_url:
			continue
		filename = f.file_url.rsplit("/", 1)[-1]

		filepath = os.path.join(path, filename)

		if filename in ignore_list:
			continue

		found = False
		for file_metadata in response.entries:
			try:
				if os.path.basename(filepath) == file_metadata.name and os.stat(
					encode(filepath)
				).st_size == int(file_metadata.size):
					found = True
					update_file_dropbox_status(f.name)
					break
			except Exception:
				error_log.append(frappe.get_traceback())

		if not found:
			try:
				upload_file_to_dropbox(filepath, dropbox_folder, dropbox_client)
				update_file_dropbox_status(f.name)
			except Exception:
				did_not_upload.append(filepath)
				error_log.append(frappe.get_traceback())


def upload_file_to_dropbox(filename, folder, dropbox_client):
	"""upload files with chunk of 15 mb to reduce session append calls"""
	if not os.path.exists(filename):
		return

	create_folder_if_not_exists(folder, dropbox_client)
	file_size = os.path.getsize(encode(filename))
	chunk_size = get_chunk_site(file_size)

	mode = dropbox.files.WriteMode.overwrite

	f = open(encode(filename), "rb")
	path = f"{folder}/{os.path.basename(filename)}"

	try:
		if file_size <= chunk_size:
			dropbox_client.files_upload(f.read(), path, mode)
		else:
			upload_session_start_result = dropbox_client.files_upload_session_start(f.read(chunk_size))
			cursor = dropbox.files.UploadSessionCursor(
				session_id=upload_session_start_result.session_id, offset=f.tell()
			)
			commit = dropbox.files.CommitInfo(path=path, mode=mode)

			while f.tell() < file_size:
				if (file_size - f.tell()) <= chunk_size:
					dropbox_client.files_upload_session_finish(f.read(chunk_size), cursor, commit)
				else:
					dropbox_client.files_upload_session_append(
						f.read(chunk_size), cursor.session_id, cursor.offset
					)
					cursor.offset = f.tell()
	except dropbox.exceptions.ApiError as e:
		if isinstance(e.error, dropbox.files.UploadError):
			error = f"File Path: {path}\n"
			error += frappe.get_traceback()
			frappe.log_error(error)
		else:
			raise


def create_folder_if_not_exists(folder, dropbox_client):
	try:
		dropbox_client.files_get_metadata(folder)
	except dropbox.exceptions.ApiError as e:
		# folder not found
		if isinstance(e.error, dropbox.files.GetMetadataError):
			dropbox_client.files_create_folder(folder)
		else:
			raise


def update_file_dropbox_status(file_name):
	frappe.db.set_value("File", file_name, "uploaded_to_dropbox", 1, update_modified=False)


def is_fresh_upload():
	file_name = frappe.db.get_value("File", {"uploaded_to_dropbox": 1}, "name")
	return not file_name


def get_uploaded_files_meta(dropbox_folder, dropbox_client):
	try:
		return dropbox_client.files_list_folder(dropbox_folder)
	except dropbox.exceptions.ApiError as e:
		# folder not found
		if isinstance(e.error, dropbox.files.ListFolderError):
			return frappe._dict({"entries": []})
		raise


def get_dropbox_client(dropbox_settings):
	dropbox_client = dropbox.Dropbox(
		oauth2_access_token=dropbox_settings["access_token"],
		oauth2_refresh_token=dropbox_settings["refresh_token"],
		app_key=dropbox_settings["app_key"],
		app_secret=dropbox_settings["app_secret"],
		timeout=None,
	)

	# checking if the access token has expired
	dropbox_client.files_list_folder("")
	if dropbox_settings["access_token"] != dropbox_client._oauth2_access_token:
		set_dropbox_token(dropbox_client._oauth2_access_token)

	return dropbox_client


def get_dropbox_settings(redirect_uri=False):
	# NOTE: access token is kept for legacy dropbox apps
	settings = frappe.get_doc("Dropbox Settings")
	app_details = {
		"app_key": settings.app_access_key or frappe.conf.dropbox_access_key,
		"app_secret": settings.get_password(fieldname="app_secret_key", raise_exception=False)
		if settings.app_secret_key
		else frappe.conf.dropbox_secret_key,
		"refresh_token": settings.get_password("dropbox_refresh_token", raise_exception=False),
		"access_token": settings.get_password("dropbox_access_token", raise_exception=False),
		"file_backup": settings.file_backup,
		"no_of_backups": settings.no_of_backups if settings.limit_no_of_backups else None,
	}

	if redirect_uri:
		app_details.update(
			{
				"redirect_uri": get_request_site_address(True)
				+ "/api/method/frappe.integrations.doctype.dropbox_settings.dropbox_settings.dropbox_auth_finish"
			}
		)

	if not (app_details["app_key"] and app_details["app_secret"]):
		raise Exception(_("Please set Dropbox access keys in site config or doctype"))

	return app_details


def delete_older_backups(dropbox_client, folder_path, to_keep):
	res = dropbox_client.files_list_folder(path=folder_path)
	files = []
	for f in res.entries:
		if isinstance(f, dropbox.files.FileMetadata) and "sql" in f.name:
			files.append(f)

	if len(files) <= to_keep:
		return

	files.sort(key=lambda item: item.client_modified, reverse=True)
	for f in files[to_keep:]:
		dropbox_client.files_delete(os.path.join(folder_path, f.name))


@frappe.whitelist()
def get_dropbox_authorize_url():
	app_details = get_dropbox_settings(redirect_uri=True)
	dropbox_oauth_flow = dropbox.DropboxOAuth2Flow(
		consumer_key=app_details["app_key"],
		redirect_uri=app_details["redirect_uri"],
		session={},
		csrf_token_session_key="dropbox-auth-csrf-token",
		consumer_secret=app_details["app_secret"],
		token_access_type="offline",
	)

	auth_url = dropbox_oauth_flow.start()

	return {"auth_url": auth_url, "args": parse_qs(urlparse(auth_url).query)}


@frappe.whitelist()
def dropbox_auth_finish():
	app_details = get_dropbox_settings(redirect_uri=True)
	callback = frappe.form_dict
	close = '<p class="text-muted">' + _("Please close this window") + "</p>"

	if not callback.state or not callback.code:
		frappe.respond_as_web_page(
			_("Dropbox Setup"),
			_("Illegal Access Token. Please try again") + close,
			indicator_color="red",
			http_status_code=frappe.AuthenticationError.http_status_code,
		)
		return

	dropbox_oauth_flow = dropbox.DropboxOAuth2Flow(
		consumer_key=app_details["app_key"],
		redirect_uri=app_details["redirect_uri"],
		session={"dropbox-auth-csrf-token": callback.state},
		csrf_token_session_key="dropbox-auth-csrf-token",
		consumer_secret=app_details["app_secret"],
	)

	token = dropbox_oauth_flow.finish({"state": callback.state, "code": callback.code})
	set_dropbox_token(token.access_token, token.refresh_token)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/app/dropbox-settings"


def set_dropbox_token(access_token, refresh_token=None):
	# NOTE: used doc object instead of db.set_value so that password field is set properly
	dropbox_settings = frappe.get_single("Dropbox Settings")
	dropbox_settings.dropbox_access_token = access_token
	if refresh_token:
		dropbox_settings.dropbox_refresh_token = refresh_token

	dropbox_settings.save()

	frappe.db.commit()
