# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""This module handles the On Demand Backup utility"""

from __future__ import print_function, unicode_literals

import os
import json
from datetime import datetime

import frappe
from frappe import _, conf
from frappe.utils import cstr, get_url, now_datetime

# backup variable for backwards compatibility
verbose = False
_verbose = verbose


class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup

		To initialize, specify (db_name, user, password, db_file_name=None, db_host="localhost")
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password, backup_path_db=None, backup_path_files=None,
		backup_path_private_files=None, db_host="localhost", db_port=None, verbose=False,
		db_type='mariadb'):
		global _verbose
		self.db_host = db_host
		self.db_port = db_port
		self.db_name = db_name
		self.db_type = db_type
		self.user = user
		self.password = password
		self.backup_path_files = backup_path_files
		self.backup_path_db = backup_path_db
		self.backup_path_private_files = backup_path_private_files

		if not self.db_port and self.db_type == 'mariadb':
			self.db_port = 3306
		elif not self.db_port and self.db_type == 'postgres':
			self.db_port = 5432

		site = frappe.local.site or frappe.generate_hash(length=8)
		self.site_slug = site.replace('.', '_')

		self.verbose = verbose
		_verbose = verbose

	def get_backup(self, older_than=24, ignore_files=False, force=False):
		"""
			Takes a new dump if existing file is old
			and sends the link to the file as email
		"""
		#Check if file exists and is less than a day old
		#If not Take Dump
		if not force:
			last_db, last_file, last_private_file, site_config_backup_path = self.get_recent_backup(older_than)
		else:
			last_db, last_file, last_private_file, site_config_backup_path = False, False, False, False

		self.todays_date = now_datetime().strftime('%Y%m%d_%H%M%S')

		if not (self.backup_path_files and self.backup_path_db and self.backup_path_private_files):
			self.set_backup_file_name()

		if not (last_db and last_file and last_private_file and site_config_backup_path):
			self.take_dump()
			self.copy_site_config()
			if not ignore_files:
				self.zip_files()

		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db
			self.backup_path_private_files = last_private_file
			self.site_config_backup_path = site_config_backup_path

	def set_backup_file_name(self):
		#Generate a random name using today's date and a 8 digit random number
		for_db = self.todays_date + "-" + self.site_slug + "-database.sql.gz"
		for_public_files = self.todays_date + "-" + self.site_slug + "-files.tar"
		for_private_files = self.todays_date + "-" + self.site_slug + "-private-files.tar"
		backup_path = get_backup_path()

		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def get_recent_backup(self, older_than):
		file_list = os.listdir(get_backup_path())
		backup_path_files = None
		backup_path_db = None
		backup_path_private_files = None
		site_config_backup_path = None

		for this_file in file_list:
			this_file = cstr(this_file)
			this_file_path = os.path.join(get_backup_path(), this_file)
			if not is_file_old(this_file_path, older_than):
				if "-private-files" in this_file_path:
					backup_path_private_files = this_file_path
				elif "-files" in this_file_path:
					backup_path_files = this_file_path
				elif "-database" in this_file_path:
					backup_path_db = this_file_path
				elif "site_config" in this_file_path:
					site_config_backup_path = this_file_path

		return (backup_path_db, backup_path_files, backup_path_private_files, site_config_backup_path)

	def zip_files(self):
		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = self.backup_path_files if folder=="public" else self.backup_path_private_files

			cmd_string = """tar -cf %s %s""" % (backup_path, files_path)
			err, out = frappe.utils.execute_in_shell(cmd_string)

			if self.verbose:
				print('Backed up files', os.path.abspath(backup_path))

	def copy_site_config(self):
		site_config_backup_path = os.path.join(
			get_backup_path(),
			"{time_stamp}-{site_slug}-site_config_backup.json".format(
				time_stamp=self.todays_date,
				site_slug=self.site_slug))
		site_config_path = os.path.join(frappe.get_site_path(), "site_config.json")
		site_config = {}
		if os.path.exists(site_config_path):
			site_config.update(frappe.get_file_json(site_config_path))
		with open(site_config_backup_path, "w") as f:
			f.write(json.dumps(site_config, indent=2))
			f.flush()
		self.site_config_backup_path = site_config_backup_path

	def take_dump(self):
		import frappe.utils

		# escape reserved characters
		args = dict([item[0], frappe.utils.esc(str(item[1]), '$ ')]
			for item in self.__dict__.copy().items())

		cmd_string = """mysqldump --single-transaction --quick --lock-tables=false -u %(user)s -p%(password)s %(db_name)s -h %(db_host)s -P %(db_port)s | gzip > %(backup_path_db)s """ % args

		if self.db_type == 'postgres':
			cmd_string = "pg_dump postgres://{user}:{password}@{db_host}:{db_port}/{db_name} | gzip > {backup_path_db}".format(
				user=args.get('user'),
				password=args.get('password'),
				db_host=args.get('db_host'),
				db_port=args.get('db_port'),
				db_name=args.get('db_name'),
				backup_path_db=args.get('backup_path_db')
			)

		err, out = frappe.utils.execute_in_shell(cmd_string)

	def send_email(self):
		"""
			Sends the link to backup file located at erpnext/backups
		"""
		from frappe.email import get_system_managers

		recipient_list = get_system_managers()
		db_backup_url = get_url(os.path.join('backups', os.path.basename(self.backup_path_db)))
		files_backup_url = get_url(os.path.join('backups', os.path.basename(self.backup_path_files)))

		msg = """Hello,

Your backups are ready to be downloaded.

1. [Click here to download the database backup](%(db_backup_url)s)
2. [Click here to download the files backup](%(files_backup_url)s)

This link will be valid for 24 hours. A new backup will be available for
download only after 24 hours.""" % {
			"db_backup_url": db_backup_url,
			"files_backup_url": files_backup_url
		}

		datetime_str = datetime.fromtimestamp(os.stat(self.backup_path_db).st_ctime)
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""

		frappe.sendmail(recipients=recipient_list, msg=msg, subject=subject)
		return recipient_list


@frappe.whitelist()
def get_backup():
	"""
		This function is executed when the user clicks on
		Toos > Download Backup
	"""
	delete_temp_backups()
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password, db_host = frappe.db.host,\
							db_type=frappe.conf.db_type, db_port=frappe.conf.db_port)
	odb.get_backup()
	recipient_list = odb.send_email()
	frappe.msgprint(_("Download link for your backup will be emailed on the following email address: {0}").format(', '.join(recipient_list)))

@frappe.whitelist()
def fetch_latest_backups():
	"""Fetches paths of the latest backup taken in the last 30 days
	Only for: System Managers

	Returns:
		dict: relative Backup Paths
	"""
	frappe.only_for("System Manager")
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name, frappe.conf.db_password, db_host=frappe.db.host, db_type=frappe.conf.db_type, db_port=frappe.conf.db_port)
	database, public, private, config = odb.get_recent_backup(older_than=24 * 30)

	return {
		"database": database,
		"public": public,
		"private": private,
		"config": config
	}

def scheduled_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, verbose=False):
	"""this function is called from scheduler
		deletes backups older than 7 days
		takes backup"""
	odb = new_backup(older_than, ignore_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=force, verbose=verbose)
	return odb

def new_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, verbose=False):
	delete_temp_backups(older_than = frappe.conf.keep_backups_for_hours or 24)
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password,
						  backup_path_db=backup_path_db, backup_path_files=backup_path_files,
						  backup_path_private_files=backup_path_private_files,
						  db_host = frappe.db.host,
						  db_port = frappe.db.port,
						  db_type = frappe.conf.db_type,
						  verbose=verbose)
	odb.get_backup(older_than, ignore_files, force=force)
	return odb

def delete_temp_backups(older_than=24):
	"""
		Cleans up the backup_link_path directory by deleting files older than 24 hours
	"""
	backup_path = get_backup_path()
	if os.path.exists(backup_path):
		file_list = os.listdir(get_backup_path())
		for this_file in file_list:
			this_file_path = os.path.join(get_backup_path(), this_file)
			if is_file_old(this_file_path, older_than):
				os.remove(this_file_path)

def is_file_old(db_file_name, older_than=24):
		"""
			Checks if file exists and is older than specified hours
			Returns ->
			True: file does not exist or file is old
			False: file is new
		"""
		if os.path.isfile(db_file_name):
			from datetime import timedelta
			#Get timestamp of the file
			file_datetime = datetime.fromtimestamp\
						(os.stat(db_file_name).st_ctime)
			if datetime.today() - file_datetime >= timedelta(hours = older_than):
				if _verbose:
					print("File is old")
				return True
			else:
				if _verbose:
					print("File is recent")
				return False
		else:
			if _verbose:
				print("File does not exist")
			return True

def get_backup_path():
	backup_path = frappe.utils.get_site_path(conf.get("backup_path", "private/backups"))
	return backup_path

def backup(with_files=False, backup_path_db=None, backup_path_files=None, quiet=False):
	"Backup"
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=True)
	return {
		"backup_path_db": odb.backup_path_db,
		"backup_path_files": odb.backup_path_files,
		"backup_path_private_files": odb.backup_path_private_files
	}


if __name__ == "__main__":
	"""
		is_file_old db_name user password db_host db_type db_port
		get_backup  db_name user password db_host db_type db_port
	"""
	import sys
	cmd = sys.argv[1]

	db_type = 'mariadb'
	try:
		db_type = sys.argv[6]
	except IndexError:
		pass

	db_port = 3306
	try:
		db_port = int(sys.argv[7])
	except IndexError:
		pass

	if cmd == "is_file_old":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		is_file_old(odb.db_file_name)

	if cmd == "get_backup":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.get_backup()

	if cmd == "take_dump":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.take_dump()

	if cmd == "send_email":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.send_email("abc.sql.gz")

	if cmd == "delete_temp_backups":
		delete_temp_backups()
