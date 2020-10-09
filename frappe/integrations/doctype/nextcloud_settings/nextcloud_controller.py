# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.backups import new_backup
from frappe.utils.background_jobs import enqueue
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size, generate_files_backup
from frappe.utils import cint, get_backups_path

import requests
import os
from rq.timeouts import JobTimeoutException
from urllib.parse import urlparse

class NextCloudController:
	def __init__(self):
		self.upload_path=False
		self.nextcloud_settings = frappe.get_doc("NextCloud Settings")
		self.backup_path = get_backups_path()

	def take_backup_nextcloud(self, retry_count=0, upload_db_backup=True):
		try:
			did_not_upload, error_log = [], []
			if cint(self.nextcloud_settings.enabled):
				validate_file_size()
				self.backup_to_nextcloud(did_not_upload, error_log, upload_db_backup)
				if did_not_upload:
					raise Exception
				if cint(self.nextcloud_settings.send_email_for_successful_backup):
					send_email(True, "NextCloud", "NextCloud Settings", "send_notifications_to")
		except JobTimeoutException:
			if retry_count < 2:
				args = {
					"retry_count": retry_count + 1,
					"upload_db_backup": False #considering till worker timeout db backup is uploaded
				}
				enqueue(self.take_backup_nextcloud, queue='long', timeout=1500, **args)
		except Exception:
			if isinstance(error_log, str):
				error_message = error_log + "\n" + frappe.get_traceback()
			else:
				file_and_error = [" - ".join(f) for f in zip(did_not_upload, list(set(error_log)))]
				error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
			send_email(False, "NextCloud", "NextCloud Settings", "send_notifications_to", error_message)

	def backup_to_nextcloud(self, did_not_upload, error_log, upload_db_backup=True,):
		if not frappe.db:
			frappe.connect()
		if upload_db_backup:
			base_url = self.make_baseurl()
			if not base_url:
				did_not_upload.append('Failed')
				error_log.append('NextCloud URL incorrect')
				return
			if self.nextcloud_settings.path_to_upload_folder:
				url = '{0}{1}'.format(base_url, self.nextcloud_settings.path_to_upload_folder)
				self.upload_path = True
			else:
				url = '{0}{1}'.format(base_url, 'Frappe Backups')
			session = self.make_session()

			# check if folder exist
			self.check_for_upload_folder(session, url)
			self.process_uploading(session, url, did_not_upload, error_log)

	def process_uploading(self, session, url, did_not_upload, error_log):

		db_backup, site_config, public_file_backup, private_file_backup = self.prepare_backup()

		db_response = upload_backup(session, url, db_backup)
		if db_response == 'Failed':
			did_not_upload.append(db_backup)
			error_log.append('Failed while uploading DB')

		site_config_response = upload_backup(session, url, site_config)
		if site_config_response == 'Failed': 
			did_not_upload.append(site_config)
			error_log.append('Failed while uploading Site Config')

		# file backup
		if cint(self.nextcloud_settings.backup_files) and db_response != 'Failed' and site_config_response != 'Failed':
			self.file_upload(session, url, public_file_backup, private_file_backup, did_not_upload, error_log)
			# if public_file_backup:
			# 	print('public_file_backup')
			# 	response_public_file = upload_backup(session, url, public_file_backup)
			# 	print(response_public_file)
			# 	if response_public_file == 'Failed': 
			# 		did_not_upload.append(public_file_backup)
			# 		error_log.append('Failed while uploading Public files')
			# if private_file_backup:
			# 	print('private_file_backup')
			# 	response_private_file = upload_backup(session, url, private_file_backup)
			# 	print(response_public_file)
			# 	if response_private_file == 'Failed': 
			# 		did_not_upload.append(private_file_backup)
			# 		error_log.append('Failed while uploading Private files')


	def file_upload(self, session, url, public_file_backup, private_file_backup, did_not_upload, error_log):
		if public_file_backup:
			response_public_file = upload_backup(session, url, public_file_backup)
			if response_public_file == 'Failed': 
				did_not_upload.append(public_file_backup)
				error_log.append('Failed while uploading Public files')
		if private_file_backup:
			response_private_file = upload_backup(session, url, private_file_backup)
			if response_private_file == 'Failed': 
				did_not_upload.append(private_file_backup)
				error_log.append('Failed while uploading Private files')

	def prepare_backup(self, db_backup=None, site_config=None, public_file_backup=None, private_file_backup=None):
		if frappe.flags.create_new_backup:
			backup = new_backup(ignore_files= True if cint(self.nextcloud_settings.backup_files) else False)
			db_backup = os.path.join(self.backup_path, os.path.basename(backup.backup_path_db))
			site_config = os.path.join(self.backup_path, os.path.basename(backup.backup_path_conf))
			if cint(self.nextcloud_settings.backup_files):
				public_file_backup = os.path.join(self.backup_path, os.path.basename(backup.backup_path_files))
				private_file_backup = os.path.join(self.backup_path, os.path.basename(backup.backup_path_private_files))

		else:
			if cint(self.nextcloud_settings.backup_files):
				db_backup, site_config, public_file_backup, private_file_backup = get_latest_backup_file(with_files=True)

				if not public_file_backup or not private_file_backup:
					generate_files_backup()
					db_backup, site_config, public_file_backup, private_file_backup = get_latest_backup_file(with_files=True)
			else:
				db_backup, site_config,  = get_latest_backup_file()

		return db_backup, site_config, public_file_backup, private_file_backup

	def make_session(self):
		session = requests.session()
		session.verify = True
		session.stream = True
		session.auth = (self.nextcloud_settings.email, self.nextcloud_settings.get_password(fieldname='password',raise_exception=False))
		session.headers.update({
			"OCS-APIRequest": "true",
		})
		return session

	def make_baseurl(self):
		vurl = urlparse(self.nextcloud_settings.nextcloud_url)
		if not vurl.scheme:
			return None
		if not vurl.netloc:
			return None
		if not vurl.port:
			port = 443 if vurl.scheme == 'https' else 80

		base_url = '{0}://{1}:{2}'.format(vurl.scheme, vurl.netloc, vurl.port if vurl.port else port)
		if self.nextcloud_settings.webdav_url.startswith('/'):
			base_url = '{0}{1}'.format(base_url, self.nextcloud_settings.webdav_url)
		else:
			base_url = '{0}/{1}'.format(base_url, self.nextcloud_settings.webdav_url)
		if not base_url.endswith('/'):
			base_url = '{0}/'.format(base_url)
		return base_url

	def check_for_upload_folder(self, session, url):
		response = session.request("PROPFIND", url, headers={"Depth": "0"}, allow_redirects=False)
		if response.status_code == 404:
			if self.upload_path:
				frappe.throw(_('Given "Path to upload folder" does not exist'))
			else:
				response = session.request("MKCOL", url, allow_redirects=False)
				if response.status_code != 201:
					frappe.throw(_('There was an error. Please try again'))

def upload_backup(session, baseurl, filebackup):
	if not os.path.exists(filebackup):
		return
	local_fileobj = filebackup
	fileobj = local_fileobj.split('/')
	dir_length = len(fileobj) - 1
	remote_fileobj=fileobj[dir_length].encode("ascii", "ignore").decode("ascii")
	if baseurl.endswith('/'):
		url = '{0}{1}'.format(baseurl, remote_fileobj)
	else:
		url = '{0}/{1}'.format(baseurl, remote_fileobj)
	if isinstance(filebackup, str):
		try:
			with open(filebackup, 'rb') as f:
				response = session.request("PUT", url, allow_redirects=False, data=f)
		except Exception as e:
			return "Failed"
	else:
		try:
			response = session.request("PUT", url, allow_redirects=False, data=filebackup)
		except Exception as e:
			return "Failed"
	if response.status_code not in (201, 204):
		return "Failed"
	else:
		return "Success"