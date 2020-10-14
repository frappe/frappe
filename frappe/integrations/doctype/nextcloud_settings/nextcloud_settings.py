# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.background_jobs import enqueue
from frappe.utils import cint, get_backups_path
from frappe.utils.backups import new_backup
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size, generate_files_backup

import requests
import os
from rq.timeouts import JobTimeoutException
from urllib.parse import urlparse

class NextCloudSettings(Document):

	upload_path = None
	session = None
	failed_uploads, error_log = [], []

	def take_backup(self, retry_count=0, upload_db_backup=True):
		try:
			if self.enabled:
				validate_file_size()
				self.backup_to_nextcloud(upload_db_backup)
				if self.error_log:
					raise Exception
				if self.send_email_for_successful_backup:
					send_email(True, "NextCloud", "NextCloud Settings", "send_notifications_to")
		except JobTimeoutException:
			if retry_count < 2:
				args = {
					"retry_count": retry_count + 1,
					"upload_db_backup": False #considering till worker timeout db backup is uploaded
				}
				enqueue(self.take_backup, queue='long', timeout=1500, **args)
		except Exception:
			if isinstance(self.error_log, str):
				error_message = self.error_log + "\n" + frappe.get_traceback()
			else:
				file_and_error = [" - ".join(f) for f in zip(self.failed_uploads if self.failed_uploads else '', list(set(self.error_log)))]
				error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
			send_email(False, "NextCloud", "NextCloud Settings", "send_notifications_to", error_message)

	def backup_to_nextcloud(self, upload_db_backup=True,):
		if not frappe.db:
			frappe.connect()
		if upload_db_backup:
			base_url = self.make_baseurl()
			if not base_url:
				self.error_log.append(_('NextCloud URL incorrect'))
				return
			self.make_upload_path(base_url)
			self.make_session()

			# check if folder exist
			self.check_for_upload_folder()
			self.process_uploading()


	def make_upload_path(self, base_url):
		'''This function checks if path is provided and depending on it makes an upload path'''
		if self.path_to_upload_folder:
			self.upload_path = '{0}{1}'.format(base_url, self.path_to_upload_folder)
		else:
			self.upload_path = '{0}{1}'.format(base_url, 'Frappe Backups')

	def process_uploading(self):
		db_backup, site_config, public_file_backup, private_file_backup = self.prepare_backup()

		db_response = self.upload_backup(db_backup)
		if db_response == 'Failed':
			self.failed_uploads.append(db_backup)
			self.error_log.append(_('Failed while uploading DB'))

		site_config_response = self.upload_backup(site_config)
		if site_config_response == 'Failed':
			self.failed_uploads.append(site_config)
			self.error_log.append(_('Failed while uploading Site Config'))

		# file backup
		if self.backup_files and db_response != 'Failed' and site_config_response != 'Failed':
			self.file_upload(public_file_backup, private_file_backup)

	def file_upload(self, public_file_backup, private_file_backup):
		if public_file_backup:
			response_public_file = self.upload_backup(public_file_backup)
			if response_public_file == 'Failed':
				self.failed_uploads.append(public_file_backup)
				self.error_log.append(_('Failed while uploading Public files'))
		if private_file_backup:
			response_private_file = self.upload_backup(private_file_backup)
			if response_private_file == 'Failed':
				self.failed_uploads.append(private_file_backup)
				self.error_log.append(_('Failed while uploading Private files'))

	def prepare_backup(self):
		odb = new_backup(ignore_files=False if self.backup_files else True, force=frappe.flags.create_new_backup)
		database, public, private, config = odb.get_recent_backup(older_than=24 * 30)
		return database, config, public, private

	def make_session(self):
		session = requests.session()
		session.verify = True
		session.stream = True
		session.auth = (self.email, 
		self.get_password(fieldname='password',raise_exception=False))
		session.headers.update({
			"OCS-APIRequest": "true",
		})
		self.session = session

	def make_baseurl(self):
		vurl = urlparse(self.nextcloud_url)
		if not vurl.scheme:
			return None
		if not vurl.netloc:
			return None
		if not vurl.port:
			port = 443 if vurl.scheme == 'https' else 80

		base_url = '{0}://{1}:{2}'.format(vurl.scheme, vurl.netloc, vurl.port if vurl.port else port)
		if self.webdav_url.startswith('/'):
			base_url = '{0}{1}'.format(base_url, self.webdav_url)
		else:
			base_url = '{0}/{1}'.format(base_url, self.webdav_url)
		if not base_url.endswith('/'):
			base_url = '{0}/'.format(base_url)
		return base_url

	def check_for_upload_folder(self):
		'''If a path is provide in NextCloud Setting, this function checks if that path exist.
		If no path is provided, this function will create a folder called "Frappe Backups" for the user.'''
		response = self.session.request("PROPFIND", self.upload_path, headers={"Depth": "0"}, allow_redirects=False)
		if response.status_code == 404:
			if self.path_to_upload_folder:
				frappe.throw(_('Given "Path to upload folder" does not exist'))
			else:
				response = self.session.request("MKCOL", self.upload_path, allow_redirects=False)
				print(response.ok)
				if not response.ok:
					frappe.throw(_('There was an error. Please try again'))

	def upload_backup(self, filebackup):
		if not os.path.exists(filebackup):
			return
		local_fileobj = filebackup
		fileobj = local_fileobj.split('/')
		dir_length = len(fileobj) - 1
		remote_fileobj=fileobj[dir_length].encode("ascii", "ignore").decode("ascii")
		if self.upload_path.endswith('/'):
			url = '{0}{1}'.format(self.upload_path, remote_fileobj)
		else:
			url = '{0}/{1}'.format(self.upload_path, remote_fileobj)
		if isinstance(filebackup, str):
			try:
				with open(filebackup, 'rb') as f:
					response = self.session.request("PUT", url, allow_redirects=False, data=f)
			except Exception as e:
				return "Failed"
		else:
			try:
				response = self.session.request("PUT", url, allow_redirects=False, data=filebackup)
			except Exception as e:
				return "Failed"
		if response.status_code not in (201, 204):
			return "Failed"
		else:
			return "Success"

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to nextcloud"""
	enqueue("frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.start_backup", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take from a few minutes upto 30 minutes."))

def daily_backup():
	take_backups_if("Daily")

def weekly_backup():
	take_backups_if("Weekly")

def take_backups_if(freq):
	if frappe.db.get_single_value("NextCloud Settings", "backup_frequency") == freq:
		start_backup()

def start_backup():
	backup = frappe.get_doc("NextCloud Settings")
	backup.take_backup()
