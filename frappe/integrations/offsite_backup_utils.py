# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import glob
import os
from frappe.utils import split_emails, get_backups_path


def send_email(success, service_name, doctype, email_field, error_status=None):
	recipients = get_recipients(doctype, email_field)
	if not recipients:
		frappe.log_error("No Email Recipient found for {0}".format(service_name),
				"{0}: Failed to send backup status email".format(service_name))
		return

	if success:
		if not frappe.db.get_value(doctype, None, "send_email_for_successful_backup"):
			return

		subject = "Backup Upload Successful"
		message = """
<h3>Backup Uploaded Successfully!</h3>
<p>Hi there, this is just to inform you that your backup was successfully uploaded to your {0} bucket. So relax!</p>""".format(service_name)

	else:
		subject = "[Warning] Backup Upload Failed"
		message = """
<h3>Backup Upload Failed!</h3>
<p>Oops, your automated backup to {0} failed.</p>
<p>Error message: {1}</p>
<p>Please contact your system manager for more information.</p>""".format(service_name, error_status)

	frappe.sendmail(recipients=recipients, subject=subject, message=message)


def get_recipients(doctype, email_field):
	if not frappe.db:
		frappe.connect()

	return split_emails(frappe.db.get_value(doctype, None, email_field))


def get_latest_backup_file(with_files=False):

	def get_latest(file_ext):
		file_list = glob.glob(os.path.join(get_backups_path(), file_ext))
		return max(file_list, key=os.path.getctime) if file_list else None

	latest_file = get_latest('*.sql.gz')
	latest_site_config = get_latest('*.json')

	if with_files:
		latest_public_file_bak = get_latest('*-files.tar')
		latest_private_file_bak = get_latest('*-private-files.tar')
		return latest_file, latest_site_config, latest_public_file_bak, latest_private_file_bak

	return latest_file, latest_site_config


def get_file_size(file_path, unit):
	if not unit:
		unit = 'MB'

	file_size = os.path.getsize(file_path)

	memory_size_unit_mapper = {'KB': 1, 'MB': 2, 'GB': 3, 'TB': 4}
	i = 0
	while i < memory_size_unit_mapper[unit]:
		file_size = file_size / 1000.0
		i += 1

	return file_size


def validate_file_size():
	frappe.flags.create_new_backup = True
	latest_file, site_config = get_latest_backup_file()
	file_size = get_file_size(latest_file, unit='GB')

	if file_size > 1:
		frappe.flags.create_new_backup = False
