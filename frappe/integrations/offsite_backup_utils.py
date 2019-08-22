# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import glob, os
from frappe.utils import cint, split_emails, get_backups_path

def send_email(success, service_name, doctype, recipients, error_status=None):
	if success:
		if frappe.db.get_value(doctype, None, "send_email_for_successful_backup") == '0':
			return

		subject = "Backup Upload Successful"
		message = """<h3>Backup Uploaded Successfully! </h3><p>Hi there, this is just to inform you
		that your backup was successfully uploaded to your {0} bucket. So relax!</p> """.format(service_name)

	else:
		subject = "[Warning] Backup Upload Failed"
		message = """<h3>Backup Upload Failed! </h3><p>Oops, your automated backup to {0} failed.
		</p> <p>Error message: {1}</p> <p>Please contact your system manager
		for more information.</p>""".format(service_name, error_status)

	frappe.sendmail(recipients=recipients, subject=subject, message=message)

def get_recipients(service_name, email_field):
	if not frappe.db:
		frappe.connect()

	if frappe.db.get_value("S3 Backup Settings", None, "notification_email"):
		return split_emails(frappe.db.get_value(service_name, None, email_field))
	else:
		return []

def get_latest_backup_file():
	list_of_files = glob.glob(os.path.join(get_backups_path(), '*.sql.gz'))
	latest_file = max(list_of_files, key=os.path.getctime)
	return latest_file

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
	latest_file = get_latest_backup_file()
	file_size = get_file_size(latest_file, unit='GB')

	if file_size > 1:
		frappe.flags.create_new_backup = False