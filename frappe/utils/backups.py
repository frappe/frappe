# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# imports - standard imports
import json
import os
from calendar import timegm
from datetime import datetime
from glob import glob

# imports - third party imports
import click

# imports - module imports
import frappe
from frappe import _, conf
from frappe.utils import get_url, now, now_datetime, get_file_size

# backup variable for backwards compatibility
verbose = False
compress = False
_verbose = verbose


class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup

		To initialize, specify (db_name, user, password, db_file_name=None, db_host="localhost")
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password, backup_path=None, backup_path_db=None,
		backup_path_files=None, backup_path_private_files=None, db_host="localhost", db_port=None,
		verbose=False, db_type='mariadb', backup_path_conf=None, compress_files=False):
		global _verbose
		self.compress_files = compress_files or compress
		self.db_host = db_host
		self.db_port = db_port
		self.db_name = db_name
		self.db_type = db_type
		self.user = user
		self.password = password
		self.backup_path = backup_path
		self.backup_path_conf = backup_path_conf
		self.backup_path_db = backup_path_db
		self.backup_path_files = backup_path_files
		self.backup_path_private_files = backup_path_private_files

		if not self.db_type:
			self.db_type = 'mariadb'

		if not self.db_port and self.db_type == 'mariadb':
			self.db_port = 3306
		elif not self.db_port and self.db_type == 'postgres':
			self.db_port = 5432

		site = frappe.local.site or frappe.generate_hash(length=8)
		self.site_slug = site.replace('.', '_')
		self.verbose = verbose
		self.setup_backup_directory()
		_verbose = verbose

	def setup_backup_directory(self):
		specified = self.backup_path or self.backup_path_db or self.backup_path_files or self.backup_path_private_files or self.backup_path_conf

		if not specified:
			backups_folder = get_backup_path()
			if not os.path.exists(backups_folder):
				os.makedirs(backups_folder, exist_ok=True)
		else:
			if self.backup_path:
				os.makedirs(self.backup_path, exist_ok=True)

			for file_path in set([self.backup_path_files, self.backup_path_db, self.backup_path_private_files, self.backup_path_conf]):
				if file_path:
					dir = os.path.dirname(file_path)
					os.makedirs(dir, exist_ok=True)

	@property
	def site_config_backup_path(self):
		# For backwards compatibility
		click.secho("BackupGenerator.site_config_backup_path has been deprecated in favour of BackupGenerator.backup_path_conf", fg="yellow")
		return getattr(self, "backup_path_conf", None)

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

		if not (self.backup_path_conf and self.backup_path_db and self.backup_path_files and self.backup_path_private_files):
			self.set_backup_file_name()

		if not (last_db and last_file and last_private_file and site_config_backup_path):
			self.take_dump()
			self.copy_site_config()
			if not ignore_files:
				self.backup_files()

		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db
			self.backup_path_private_files = last_private_file
			self.backup_path_conf = site_config_backup_path

	def set_backup_file_name(self):
		#Generate a random name using today's date and a 8 digit random number
		for_conf = self.todays_date + "-" + self.site_slug + "-site_config_backup.json"
		for_db = self.todays_date + "-" + self.site_slug + "-database.sql.gz"
		ext = "tgz" if self.compress_files else "tar"

		for_public_files = self.todays_date + "-" + self.site_slug + "-files." + ext
		for_private_files = self.todays_date + "-" + self.site_slug + "-private-files." + ext
		backup_path = self.backup_path or get_backup_path()

		if not self.backup_path_conf:
			self.backup_path_conf = os.path.join(backup_path, for_conf)
		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def get_recent_backup(self, older_than):
		backup_path = get_backup_path()

		file_type_slugs = {
			"database": "*-{}-database.sql.gz",
			"public": "*-{}-files.tar",
			"private": "*-{}-private-files.tar",
			"config": "*-{}-site_config_backup.json",
		}

		def backup_time(file_path):
			file_name = file_path.split(os.sep)[-1]
			file_timestamp = file_name.split("-")[0]
			return timegm(datetime.strptime(file_timestamp, "%Y%m%d_%H%M%S").utctimetuple())

		def get_latest(file_pattern):
			file_pattern = os.path.join(backup_path, file_pattern.format(self.site_slug))
			file_list = glob(file_pattern)
			if file_list:
				return max(file_list, key=backup_time)

		def old_enough(file_path):
			if file_path:
				if not os.path.isfile(file_path) or is_file_old(file_path, older_than):
					return None
				return file_path

		latest_backups = {
			file_type: get_latest(pattern)
			for file_type, pattern in file_type_slugs.items()
		}

		recent_backups = {
			file_type: old_enough(file_name) for file_type, file_name in latest_backups.items()
		}

		return (
			recent_backups.get("database"),
			recent_backups.get("public"),
			recent_backups.get("private"),
			recent_backups.get("config"),
		)

	def zip_files(self):
		# For backwards compatibility - pre v13
		click.secho("BackupGenerator.zip_files has been deprecated in favour of BackupGenerator.backup_files", fg="yellow")
		return self.backup_files()

	def get_summary(self):
		summary = {
			"config": {
				"path": self.backup_path_conf,
				"size": get_file_size(self.backup_path_conf, format=True)
			},
			"database": {
				"path": self.backup_path_db,
				"size": get_file_size(self.backup_path_db, format=True)
			}
		}

		if os.path.exists(self.backup_path_files) and os.path.exists(self.backup_path_private_files):
			summary.update({
				"public": {
					"path": self.backup_path_files,
					"size": get_file_size(self.backup_path_files, format=True)
				},
				"private": {
					"path": self.backup_path_private_files,
					"size": get_file_size(self.backup_path_private_files, format=True)
				}
			})

		return summary

	def print_summary(self):
		backup_summary = self.get_summary()
		print("Backup Summary for {0} at {1}".format(frappe.local.site, now()))

		for _type, info in backup_summary.items():
			print("{0:8}: {1:85} {2}".format(_type.title(), info["path"], info["size"]))

	def backup_files(self):
		import subprocess

		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = self.backup_path_files if folder=="public" else self.backup_path_private_files

			if self.compress_files:
				cmd_string = "tar cf - {1} | gzip > {0}"
			else:
				cmd_string = "tar -cf {0} {1}"
			output = subprocess.check_output(cmd_string.format(backup_path, files_path), shell=True)

			if self.verbose and output:
				print(output.decode("utf8"))

	def copy_site_config(self):
		site_config_backup_path = self.backup_path_conf
		site_config_path = os.path.join(frappe.get_site_path(), "site_config.json")

		with open(site_config_backup_path, "w") as n, open(site_config_path) as c:
			n.write(c.read())

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
	odb = BackupGenerator(
		frappe.conf.db_name,
		frappe.conf.db_name,
		frappe.conf.db_password,
		db_host=frappe.db.host,
		db_type=frappe.conf.db_type,
		db_port=frappe.conf.db_port,
	)
	database, public, private, config = odb.get_recent_backup(older_than=24 * 30)

	return {
		"database": database,
		"public": public,
		"private": private,
		"config": config
	}


def scheduled_backup(older_than=6, ignore_files=False, backup_path=None, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, backup_path_conf=None, force=False, verbose=False, compress=False):
	"""this function is called from scheduler
		deletes backups older than 7 days
		takes backup"""
	odb = new_backup(older_than, ignore_files, backup_path=backup_path, backup_path_db=backup_path_db, backup_path_files=backup_path_files, backup_path_private_files=backup_path_private_files, backup_path_conf=backup_path_conf, force=force, verbose=verbose, compress=compress)
	return odb

def new_backup(older_than=6, ignore_files=False, backup_path=None, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, backup_path_conf=None, force=False, verbose=False, compress=False):
	delete_temp_backups(older_than = frappe.conf.keep_backups_for_hours or 24)
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password,
						  backup_path=backup_path,
						  backup_path_db=backup_path_db,
						  backup_path_files=backup_path_files,
						  backup_path_private_files=backup_path_private_files,
						  backup_path_conf=backup_path_conf,
						  db_host = frappe.db.host,
						  db_port = frappe.db.port,
						  db_type = frappe.conf.db_type,
						  verbose=verbose,
						  compress_files=compress)
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

def backup(with_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, backup_path_conf=None, quiet=False):
	"Backup"
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, backup_path_private_files=backup_path_private_files, backup_path_conf=backup_path_conf, force=True)
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
