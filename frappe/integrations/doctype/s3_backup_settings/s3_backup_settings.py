# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import print_function, unicode_literals
import os
import os.path
import frappe
import boto3
from frappe import _
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.background_jobs import enqueue
from rq.timeouts import JobTimeoutException
from botocore.exceptions import ClientError


class S3BackupSettings(Document):

	def validate(self):
		if not self.enabled:
			return

		if not self.endpoint_url:
			self.endpoint_url = 'https://s3.amazonaws.com'
		conn = boto3.client(
			's3',
			aws_access_key_id=self.access_key_id,
			aws_secret_access_key=self.get_password('secret_access_key'),
			endpoint_url=self.endpoint_url
		)

		bucket_lower = str(self.bucket)

		try:
			conn.list_buckets()

		except ClientError:
			frappe.throw(_("Invalid Access Key ID or Secret Access Key."))

		try:
			# Head_bucket returns a 200 OK if the bucket exists and have access to it.
			conn.head_bucket(Bucket=bucket_lower)
		except ClientError as e:
			error_code = e.response['Error']['Code']
			if error_code == '403':
				frappe.throw(_("Do not have permission to access {0} bucket.").format(bucket_lower))
			else:   # '400'-Bad request or '404'-Not Found return
				# try to create bucket
				conn.create_bucket(Bucket=bucket_lower, CreateBucketConfiguration={
					'LocationConstraint': self.region})


@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to s3"""
	enqueue("frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))


def take_backups_daily():
	take_backups_if("Daily")


def take_backups_weekly():
	take_backups_if("Weekly")


def take_backups_monthly():
	take_backups_if("Monthly")

def take_backups_if(freq):
	if cint(frappe.db.get_value("S3 Backup Settings", None, "enabled")):
		if frappe.db.get_value("S3 Backup Settings", None, "frequency") == freq:
			take_backups_s3()

@frappe.whitelist()
def take_backups_s3(retry_count=0):
	try:
		validate_file_size()
		backup_to_s3()
		send_email(True, "Amazon S3", "S3 Backup Settings", "notify_email")
	except JobTimeoutException:
		if retry_count < 2:
			args = {
				"retry_count": retry_count + 1
			}
			enqueue("frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3",
				queue='long', timeout=1500, **args)
		else:
			notify()
	except Exception:
		notify()


def notify():
	error_message = frappe.get_traceback()
	send_email(False, 'Amazon S3', "S3 Backup Settings", "notify_email", error_message)


def backup_to_s3():
	from frappe.utils.backups import new_backup
	from frappe.utils import get_backups_path

	doc = frappe.get_single("S3 Backup Settings")
	bucket = doc.bucket
	backup_files = cint(doc.backup_files)

	conn = boto3.client(
			's3',
			aws_access_key_id=doc.access_key_id,
			aws_secret_access_key=doc.get_password('secret_access_key'),
			endpoint_url=doc.endpoint_url or 'https://s3.amazonaws.com'
			)

	if frappe.flags.create_new_backup:
		backup = new_backup(ignore_files=False, backup_path_db=None,
						backup_path_files=None, backup_path_private_files=None, force=True)
		db_filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
		site_config = os.path.join(get_backups_path(), os.path.basename(backup.site_config_backup_path))
		if backup_files:
			files_filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_files))
			private_files = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_private_files))
	else:
		if backup_files:
			db_filename, site_config, files_filename, private_files = get_latest_backup_file(with_files=backup_files)
		else:
			db_filename, site_config = get_latest_backup_file()

	folder = os.path.basename(db_filename)[:15] + '/'
	# for adding datetime to folder name

	upload_file_to_s3(db_filename, folder, conn, bucket)
	upload_file_to_s3(site_config, folder, conn, bucket)
	if backup_files:
		upload_file_to_s3(private_files, folder, conn, bucket)
		upload_file_to_s3(files_filename, folder, conn, bucket)
	delete_old_backups(doc.backup_limit, bucket)


def upload_file_to_s3(filename, folder, conn, bucket):
	destpath = os.path.join(folder, os.path.basename(filename))
	try:
		print("Uploading file:", filename)
		conn.upload_file(filename, bucket, destpath)

	except Exception as e:
		frappe.log_error()
		print("Error uploading: %s" % (e))


def delete_old_backups(limit, bucket):
	all_backups = []
	doc = frappe.get_single("S3 Backup Settings")
	backup_limit = int(limit)

	s3 = boto3.resource(
			's3',
			aws_access_key_id=doc.access_key_id,
			aws_secret_access_key=doc.get_password('secret_access_key'),
			endpoint_url=doc.endpoint_url or 'https://s3.amazonaws.com'
			)
	bucket = s3.Bucket(bucket)
	objects = bucket.meta.client.list_objects_v2(Bucket=bucket.name, Delimiter='/')
	if objects:
		for obj in objects.get('CommonPrefixes'):
			all_backups.append(obj.get('Prefix'))

	oldest_backup = sorted(all_backups)[0]

	if len(all_backups) > backup_limit:
		print("Deleting Backup: {0}".format(oldest_backup))
		for obj in bucket.objects.filter(Prefix=oldest_backup):
			# delete all keys that are inside the oldest_backup
			s3.Object(bucket.name, obj.key).delete()
