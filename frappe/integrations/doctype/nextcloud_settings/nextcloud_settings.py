# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.backups import new_backup
from frappe.utils.background_jobs import enqueue
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size
from frappe.utils import cint, get_backups_path, encode

import requests
import os
from rq.timeouts import JobTimeoutException

class NextcloudSettings(Document):
	def validate(self):
		if not self.enabled:
			return

		if self.enabled:
			if (not self.email or self.email == "" 
				or not self.password or self.password == "" 
				or not self.domain_url or self.domain_url == "" 
				or not self.webdav_url or self.webdav_url == ""
				or not self.send_notifications_to or self.send_notifications_to == "" 
				or not self.backup_frequency or self.backup_frequency == ""):
				frappe.throw(_('If Nexcloud is enabled, the data is mandatory: email, Password, Domain URL, Webdav URL, Send Notifications To and Backup Frequency'))

def make_session(email, password):
	session = requests.session()
	session.verify = True
	session.stream = True
	session.auth = (email, password)
	session.headers.update({
		"OCS-APIRequest": "true",
	})
	return session

def make_baseurl(domain_url, webdav_url):
	port = None
	vurl = domain_url.replace("//","").split(":")
	if vurl[0] == "http" or vurl[0] == "https":
		protocol = vurl[0]
		host = vurl[1]
		if len(vurl) == 3:
			port = vurl[2]

	if not port:
		port = 443 if protocol == 'https' else 80
	baseurl = '{0}://{1}:{2}'.format(protocol, host, port)
	if webdav_url.startswith('/'):
		url = '{0}{1}'.format(baseurl, webdav_url)
	else:
		url = '{0}/{1}'.format(baseurl, webdav_url)
	if url.endswith('/'):
		pass
	else:
		url = '{0}/'.format(url)

	return url

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to nextcloud"""
	enqueue("frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.take_backup_nextcloud", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))

def take_backups_daily():
	take_backups_if("Daily")

def take_backups_weekly():
	take_backups_if("Weekly")

def take_backups_if(freq):
	if frappe.db.get_value("Nextcloud Settings", None, "backup_frequency") == freq:
		take_backup_nextcloud()

def take_backup_nextcloud(retry_count=0, upload_db_backup=True):
	did_not_upload, error_log = [], []
	try:
		if cint(frappe.db.get_value("Nextcloud Settings", None, "enabled")):
			validate_file_size()
			ignore_files = True
			if cint(frappe.db.get_value("Nextcloud Settings", None, "backup_files")):
				ignore_files = False	
			did_not_upload, error_log = backup_to_nextcloud(upload_db_backup, ignore_files)
			if did_not_upload: raise Exception
			if cint(frappe.db.get_value("Nextcloud Settings", None, "send_email_for_successful_backup")):
				send_email(True, "Nextcloud", "Nextcloud Settings", "send_notifications_to")
	except JobTimeoutException:
		if retry_count < 2:
			args = {
				"retry_count": retry_count + 1,
				"upload_db_backup": False #considering till worker timeout db backup is uploaded
			}
			enqueue("frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.take_backup_to_nextcloud",
				queue='long', timeout=1500, **args)
	except Exception:
		if isinstance(error_log, str):
			error_message = error_log + "\n" + frappe.get_traceback()
		else:
			file_and_error = [" - ".join(f) for f in zip(did_not_upload, error_log)]
			error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
		send_email(False, "Nextcloud", "Nextcloud Settings", "send_notifications_to", error_message)

def backup_to_nextcloud(upload_db_backup=True, ignore_files=True):
	if not frappe.db:
		frappe.connect()
	db_response, site_config_response = "", ""
	if upload_db_backup:
		did_not_upload, error_log = [], []
		path_provided = False
		nextcloud_settings = frappe.get_doc("Nextcloud Settings")
		domain_url = nextcloud_settings.domain_url
		webdav_url = nextcloud_settings.webdav_url
		email = nextcloud_settings.email
		password = nextcloud_settings.get_password(fieldname='password',raise_exception=False)
		base_url = make_baseurl(domain_url, webdav_url)
		if nextcloud_settings.path_to_upload_folder:
			url = '{0}{1}'.format(base_url, nextcloud_settings.path_to_upload_folder)
			path_provided = True
		else:
			url = '{0}{1}'.format(base_url, 'ERPNext Backups')
		session = make_session(email, password)

		# check if folder exist
		check_for_upload_folder(session, url, path_provided)
		if frappe.flags.create_new_backup:
			backup = new_backup(ignore_files=ignore_files)
			db_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
			site_config = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_conf))
		else:
			db_backup, site_config = get_latest_backup_file()
		db_response = upload_backup(session, url, db_backup)
		if db_response == 'Failed': 
			did_not_upload.append(db_backup)
			error_log.append('Failed while uploading DB')
		site_config_response = upload_backup(session, url, site_config)
		if site_config_response == 'Failed': 
			did_not_upload.append(site_config)
			error_log.append('Failed while uploading Site Config')

		# file backup
		if not ignore_files and db_response != 'Failed' and site_config_response != 'Failed':
			public_file_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_files))
			response_public_file = upload_backup(session, url, public_file_backup)
			if response_public_file == 'Failed': 
				did_not_upload.append(public_file_backup)
				error_log.append('Failed while uploading Public files')
			private_file_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_private_files))
			response_private_file = upload_backup(session, url, private_file_backup)
			if response_private_file == 'Failed': 
				did_not_upload.append(private_file_backup)
				error_log.append('Failed while uploading Private files')
	return did_not_upload, list(set(error_log))

def check_for_upload_folder(session, baseurl, path_provided):
	response = session.request("PROPFIND", baseurl, headers={"Depth": "0"}, allow_redirects=False)
	if response.status_code == 404:
		if path_provided:
			frappe.throw(_('Given "Path to upload folder" does not exist'))
		else:
			response = session.request("MKCOL", baseurl, allow_redirects=False)
			if response.status_code != 201:
				frappe.throw(_('There was an error. Please try again'))

def upload_backup(session, baseurl, filebackup):
	local_fileobj = filebackup
	fileobj = local_fileobj.split('/')
	dir_length = len(fileobj) - 1
	remote_fileobj=fileobj[dir_length].encode("ascii", "ignore").decode("ascii")
	if baseurl.endswith('/'):
		url = '{0}{1}'.format(baseurl, remote_fileobj)
	else:
		url = '{0}/{1}'.format(baseurl, remote_fileobj)
	if isinstance(filebackup, str):
		with open(filebackup, 'rb') as f:
			response = session.request("PUT", url, allow_redirects=False, data=f)
	else:
		response = session.request("PUT", url, allow_redirects=False, data=filebackup)
	if response.status_code not in (201, 204):
		return 'Failed'
	else:
		return 'Success'
