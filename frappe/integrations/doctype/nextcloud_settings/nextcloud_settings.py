# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.backups import new_backup
from frappe.utils.background_jobs import enqueue
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size, generate_files_backup
from frappe.utils import cint, get_backups_path

import requests
import os
from rq.timeouts import JobTimeoutException
from urllib.parse import urlparse

class NextCloudSettings(Document):

	def validate(self):
		if not self.enabled:
			return

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to nextcloud"""
	enqueue("frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.start_backup", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))

def take_backups_daily():
	take_backups_if("Daily")

def take_backups_weekly():
	take_backups_if("Weekly")

def take_backups_if(freq):
	if frappe.db.get_value("NextCloud Settings", None, "backup_frequency") == freq:
		start_backup()

def start_backup():
	backup = NextCloudController()
	backup.take_backup_nextcloud()

class NextCloudController():

	def __init__(self, ignore_files=True, db_response="", site_config_response="",
		did_not_upload=[], error_log=[], path_provided = False, nextcloud_settings=None, nextcloud_url=None,
		webdav_url=None, email=None, password=None, base_url=None, url=None, session=None):
		self.ignore_files = ignore_files
		self.db_response = db_response
		self.site_config_response = site_config_response
		self.did_not_upload = did_not_upload
		self.error_log = error_log
		self.path_provided = path_provided
		self.nextcloud_settings = nextcloud_settings
		self.nextcloud_url = nextcloud_url
		self.webdav_url = webdav_url
		self.email = email
		self.password = password
		self.base_url = base_url
		self.url = url
		self.session = session

	def take_backup_nextcloud(self, retry_count=0, upload_db_backup=True):
		try:
			if cint(frappe.db.get_value("NextCloud Settings", None, "enabled")):
				validate_file_size()
				if cint(frappe.db.get_value("NextCloud Settings", None, "backup_files")):
					self.ignore_files = False
				self.backup_to_nextcloud(upload_db_backup)
				if self.did_not_upload:
					raise Exception
				if cint(frappe.db.get_value("NextCloud Settings", None, "send_email_for_successful_backup")):
					send_email(True, "NextCloud", "NextCloud Settings", "send_notifications_to")
		except JobTimeoutException:
			if retry_count < 2:
				args = {
					"retry_count": retry_count + 1,
					"upload_db_backup": False #considering till worker timeout db backup is uploaded
				}
				enqueue(self.take_backup_nextcloud, queue='long', timeout=1500, **args)
		except Exception:
			if isinstance(self.error_log, str):
				error_message = self.error_log + "\n" + frappe.get_traceback()
			else:
				file_and_error = [" - ".join(f) for f in zip(self.did_not_upload, list(set(self.error_log)))]
				error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
			send_email(False, "NextCloud", "NextCloud Settings", "send_notifications_to", error_message)

	def backup_to_nextcloud(self, upload_db_backup=True):
		if not frappe.db:
			frappe.connect()
		if upload_db_backup:
			self.get_account_details()
			if not self.base_url:
				self.did_not_upload.append('Failed')
				self.error_log.append('NextCloud URL incorrect')
				return
			if self.nextcloud_settings.path_to_upload_folder:
				self.url = '{0}{1}'.format(self.base_url, self.nextcloud_settings.path_to_upload_folder)
				self.path_provided = True
			else:
				self.url = '{0}{1}'.format(self.base_url, 'Frappe Backups')
			self.make_session()

			# check if folder exist
			self.check_for_upload_folder()
			self.process_uploading()

	def get_account_details(self):
		self.nextcloud_settings = frappe.get_doc("NextCloud Settings")
		self.nextcloud_url = self.nextcloud_settings.nextcloud_url
		self.webdav_url = self.nextcloud_settings.webdav_url
		self.email = self.nextcloud_settings.email
		self.password = self.nextcloud_settings.get_password(fieldname='password',raise_exception=False)
		self.make_baseurl()

	def make_baseurl(self):
		vurl = urlparse(self.nextcloud_url)
		if not vurl.scheme:
			return
		if not vurl.netloc:
			return
		if not vurl.port:
			port = 443 if vurl.scheme == 'https' else 80

		baseurl = '{0}://{1}:{2}'.format(vurl.scheme, vurl.netloc, vurl.port if vurl.port else port)
		if self.webdav_url.startswith('/'):
			self.base_url = '{0}{1}'.format(baseurl, self.webdav_url)
		else:
			self.base_url = '{0}/{1}'.format(baseurl, self.webdav_url)
		if not self.base_url.endswith('/'):
			self.base_url = '{0}/'.format(self.base_url)

	def make_session(self):
		self.session = requests.session()
		self.session.verify = True
		self.session.stream = True
		self.session.auth = (self.email, self.password)
		self.session.headers.update({
			"OCS-APIRequest": "true",
		})

	def check_for_upload_folder(self):
		response = self.session.request("PROPFIND", self.url, headers={"Depth": "0"}, allow_redirects=False)
		if response.status_code == 404:
			if self.path_provided:
				frappe.throw(_('Given "Path to upload folder" does not exist'))
			else:
				response = self.session.request("MKCOL", self.url, allow_redirects=False)
				if response.status_code != 201:
					frappe.throw(_('There was an error. Please try again'))

	def process_uploading(self):
		if frappe.flags.create_new_backup:
			backup = new_backup(ignore_files=self.ignore_files)
			db_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
			site_config = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_conf))
			if not self.ignore_files:
				public_file_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_files))
				private_file_backup = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_private_files))

		else:
			if not self.ignore_files:
				db_backup, site_config, public_file_backup, private_file_backup = get_latest_backup_file(with_files=True)

				if not public_file_backup or not private_file_backup:
					generate_files_backup()
					db_backup, site_config, public_file_backup, private_file_backup = get_latest_backup_file(with_files=True)
			else:
				db_backup, site_config,  = get_latest_backup_file()
	
		db_response = upload_backup(self.session, self.url, db_backup)
		if db_response == 'Failed':
			self.did_not_upload.append(db_backup)
			self.error_log.append('Failed while uploading DB')

		site_config_response = upload_backup(self.session, self.url, site_config)
		if site_config_response == 'Failed': 
			self.did_not_upload.append(site_config)
			self.error_log.append('Failed while uploading Site Config')

		# file backup
		if not self.ignore_files and db_response != 'Failed' and site_config_response != 'Failed':
			if public_file_backup:
				response_public_file = upload_backup(self.session, self.url, public_file_backup)
				if response_public_file == 'Failed': 
					self.did_not_upload.append(public_file_backup)
					self.error_log.append('Failed while uploading Public files')
			if private_file_backup:
				response_private_file = upload_backup(self.session, self.url, private_file_backup)
				if response_private_file == 'Failed': 
					self.did_not_upload.append(private_file_backup)
					self.error_log.append('Failed while uploading Private files')

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
		return "Failed"
	else:
		return "Success"

