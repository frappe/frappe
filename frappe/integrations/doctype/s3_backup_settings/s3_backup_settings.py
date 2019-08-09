# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import print_function, unicode_literals
import os
import os.path
import frappe
import boto3
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, split_emails
from frappe.utils.background_jobs import enqueue
from rq.timeouts import JobTimeoutException
from botocore.exceptions import ClientError

class S3BackupSettings(Document):

	def validate(self):
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
			conn.create_bucket(Bucket=bucket_lower, CreateBucketConfiguration={
				'LocationConstraint': self.region})
		except ClientError:
			frappe.throw(_("Unable to create bucket: {0}. Change it to a more unique name.").format(bucket_lower))


@frappe.whitelist()
def take_backup():
	"Enqueue longjob for taking backup to s3"
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
		backup_to_s3()
		send_email(True, "S3 Backup Settings")
	except JobTimeoutException:
		if retry_count < 2:
			args = {
				"retry_count" :retry_count + 1
			}
			enqueue("frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3",
				queue='long', timeout=1500, **args)
		else:
			notify()
	except Exception:
		notify()

def notify():
	error_message = frappe.get_traceback()
	frappe.errprint(error_message)
	send_email(False, "S3 Backup Settings", error_message)

def send_email(success, service_name, error_status=None):
	if success:
		if frappe.db.get_value("S3 Backup Settings", None, "send_email_for_successful_backup") == '0':
			return

		subject = "Backup Upload Successful"
		message = """<h3>Backup Uploaded Successfully! </h3><p>Hi there, this is just to inform you
		that your backup was successfully uploaded to your Amazon S3 bucket. So relax!</p> """

	else:
		subject = "[Warning] Backup Upload Failed"
		message = """<h3>Backup Upload Failed! </h3><p>Oops, your automated backup to Amazon S3 failed.
		</p> <p>Error message: %s</p> <p>Please contact your system manager
		for more information.</p>""" % error_status

	if not frappe.db:
		frappe.connect()

	if frappe.db.get_value("S3 Backup Settings", None, "notification_email"):
		recipients = split_emails(frappe.db.get_value("S3 Backup Settings", None, "notification_email"))
		frappe.sendmail(recipients=recipients, subject=subject, message=message)


def backup_to_s3():
	from frappe.utils.backups import new_backup
	from frappe.utils import get_backups_path

	doc = frappe.get_single("S3 Backup Settings")
	bucket = doc.bucket

	conn = boto3.client(
			's3',
			aws_access_key_id=doc.access_key_id,
			aws_secret_access_key=doc.get_password('secret_access_key'),
			endpoint_url=doc.endpoint_url or 'https://s3.amazonaws.com'
			)

	backup = new_backup(ignore_files=False, backup_path_db=None,
						backup_path_files=None, backup_path_private_files=None, force=True)
	db_filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
	files_filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_files))
	private_files = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_private_files))
	folder = os.path.basename(db_filename)[:15] + '/'
	# for adding datetime to folder name

	upload_file_to_s3(db_filename, folder, conn, bucket)
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
	all_backups = list()
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
