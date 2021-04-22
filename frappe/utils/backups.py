# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# imports - standard imports
import gzip
import os
from calendar import timegm
from datetime import datetime
from glob import glob
from shutil import which

# imports - third party imports
import click

# imports - module imports
import frappe
from frappe import _, conf
from frappe.utils import get_file_size, get_url, now, now_datetime, cint

# backup variable for backwards compatibility
verbose = False
compress = False
_verbose = verbose
base_tables = ["__Auth", "__global_search", "__UserSettings"]


class BackupGenerator:
	"""
	This class contains methods to perform On Demand Backup

	To initialize, specify (db_name, user, password, db_file_name=None, db_host="localhost")
	If specifying db_file_name, also append ".sql.gz"
	"""

	def __init__(
		self,
		db_name,
		user,
		password,
		backup_path=None,
		backup_path_db=None,
		backup_path_files=None,
		backup_path_private_files=None,
		db_host="localhost",
		db_port=None,
		db_type="mariadb",
		backup_path_conf=None,
		ignore_conf=False,
		compress_files=False,
		include_doctypes="",
		exclude_doctypes="",
		verbose=False,
	):
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
		self.ignore_conf = ignore_conf
		self.include_doctypes = include_doctypes
		self.exclude_doctypes = exclude_doctypes
		self.partial = False

		if not self.db_type:
			self.db_type = "mariadb"

		if not self.db_port:
			if self.db_type == "mariadb":
				self.db_port = 3306
			if self.db_type == "postgres":
				self.db_port = 5432

		site = frappe.local.site or frappe.generate_hash(length=8)
		self.site_slug = site.replace(".", "_")
		self.verbose = verbose
		self.setup_backup_directory()
		self.setup_backup_tables()
		_verbose = verbose

	def setup_backup_directory(self):
		specified = (
			self.backup_path
			or self.backup_path_db
			or self.backup_path_files
			or self.backup_path_private_files
			or self.backup_path_conf
		)

		if not specified:
			backups_folder = get_backup_path()
			if not os.path.exists(backups_folder):
				os.makedirs(backups_folder, exist_ok=True)
		else:
			if self.backup_path:
				os.makedirs(self.backup_path, exist_ok=True)

			for file_path in set(
				[
					self.backup_path_files,
					self.backup_path_db,
					self.backup_path_private_files,
					self.backup_path_conf,
				]
			):
				if file_path:
					dir = os.path.dirname(file_path)
					os.makedirs(dir, exist_ok=True)

	def setup_backup_tables(self):
		"""Sets self.backup_includes, self.backup_excludes based on passed args"""
		existing_doctypes = set([x.name for x in frappe.get_all("DocType")])

		def get_tables(doctypes):
			tables = []
			for doctype in doctypes:
				if doctype and doctype in existing_doctypes:
					if doctype.startswith("tab"):
						tables.append(doctype)
					else:
						tables.append("tab" + doctype)
			return tables

		passed_tables = {
			"include": get_tables(self.include_doctypes.strip().split(",")),
			"exclude": get_tables(self.exclude_doctypes.strip().split(",")),
		}
		specified_tables = get_tables(frappe.conf.get("backup", {}).get("includes", []))
		include_tables = (specified_tables + base_tables) if specified_tables else []

		conf_tables = {
			"include": include_tables,
			"exclude": get_tables(frappe.conf.get("backup", {}).get("excludes", [])),
		}

		self.backup_includes = passed_tables["include"]
		self.backup_excludes = passed_tables["exclude"]

		if not (self.backup_includes or self.backup_excludes) and not self.ignore_conf:
			self.backup_includes = self.backup_includes or conf_tables["include"]
			self.backup_excludes = self.backup_excludes or conf_tables["exclude"]

		self.partial = (self.backup_includes or self.backup_excludes) and not self.ignore_conf

	@property
	def site_config_backup_path(self):
		# For backwards compatibility
		click.secho(
			"BackupGenerator.site_config_backup_path has been deprecated in favour of"
			" BackupGenerator.backup_path_conf",
			fg="yellow",
		)
		return getattr(self, "backup_path_conf", None)

	def get_backup(self, older_than=24, ignore_files=False, force=False):
		"""
		Takes a new dump if existing file is old
		and sends the link to the file as email
		"""
		# Check if file exists and is less than a day old
		# If not Take Dump
		if not force:
			(
				last_db,
				last_file,
				last_private_file,
				site_config_backup_path,
			) = self.get_recent_backup(older_than)
		else:
			last_db, last_file, last_private_file, site_config_backup_path = (
				False,
				False,
				False,
				False,
			)

		self.todays_date = now_datetime().strftime("%Y%m%d_%H%M%S")

		if not (
			self.backup_path_conf
			and self.backup_path_db
			and self.backup_path_files
			and self.backup_path_private_files
		):
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
		partial = "-partial" if self.partial else ""
		ext = "tgz" if self.compress_files else "tar"

		for_conf = f"{self.todays_date}-{self.site_slug}-site_config_backup.json"
		for_db = f"{self.todays_date}-{self.site_slug}{partial}-database.sql.gz"
		for_public_files = f"{self.todays_date}-{self.site_slug}-files.{ext}"
		for_private_files = f"{self.todays_date}-{self.site_slug}-private-files.{ext}"
		backup_path = self.backup_path or get_backup_path()

		if not self.backup_path_conf:
			self.backup_path_conf = os.path.join(backup_path, for_conf)
		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def get_recent_backup(self, older_than, partial=False):
		backup_path = get_backup_path()

		file_type_slugs = {
			"database": "*-{{}}-{}database.sql.gz".format('*' if partial else ''),
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
			file_type: get_latest(pattern) for file_type, pattern in file_type_slugs.items()
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
		click.secho(
			"BackupGenerator.zip_files has been deprecated in favour of"
			" BackupGenerator.backup_files",
			fg="yellow",
		)
		return self.backup_files()

	def get_summary(self):
		summary = {
			"config": {
				"path": self.backup_path_conf,
				"size": get_file_size(self.backup_path_conf, format=True),
			},
			"database": {
				"path": self.backup_path_db,
				"size": get_file_size(self.backup_path_db, format=True),
			},
		}

		if os.path.exists(self.backup_path_files) and os.path.exists(
			self.backup_path_private_files
		):
			summary.update(
				{
					"public": {
						"path": self.backup_path_files,
						"size": get_file_size(self.backup_path_files, format=True),
					},
					"private": {
						"path": self.backup_path_private_files,
						"size": get_file_size(self.backup_path_private_files, format=True),
					},
				}
			)

		return summary

	def print_summary(self):
		backup_summary = self.get_summary()
		print("Backup Summary for {0} at {1}".format(frappe.local.site, now()))

		title = max([len(x) for x in backup_summary])
		path = max([len(x["path"]) for x in backup_summary.values()])

		for _type, info in backup_summary.items():
			template = "{{0:{0}}}: {{1:{1}}} {{2}}".format(title, path)
			print(template.format(_type.title(), info["path"], info["size"]))

	def backup_files(self):
		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = (
				self.backup_path_files if folder == "public" else self.backup_path_private_files
			)

			if self.compress_files:
				cmd_string = "tar cf - {1} | gzip > {0}"
			else:
				cmd_string = "tar -cf {0} {1}"

			frappe.utils.execute_in_shell(
				cmd_string.format(backup_path, files_path),
				verbose=self.verbose,
				low_priority=True
			)

	def copy_site_config(self):
		site_config_backup_path = self.backup_path_conf
		site_config_path = os.path.join(frappe.get_site_path(), "site_config.json")

		with open(site_config_backup_path, "w") as n, open(site_config_path) as c:
			n.write(c.read())

	def take_dump(self):
		import frappe.utils
		from frappe.utils.change_log import get_app_branch

		db_exc = {
			"mariadb": ("mysqldump", which("mysqldump")),
			"postgres": ("pg_dump", which("pg_dump")),
		}[self.db_type]
		gzip_exc = which("gzip")

		if not (gzip_exc and db_exc[1]):
			_exc = "gzip" if not gzip_exc else db_exc[0]
			frappe.throw(
				f"{_exc} not found in PATH! This is required to take a backup.",
				exc=frappe.ExecutableNotFound
			)
		db_exc = db_exc[0]

		database_header_content = [
			f"Backup generated by Frappe {frappe.__version__} on branch {get_app_branch('frappe') or 'N/A'}",
			"",
		]

		# escape reserved characters
		args = frappe._dict(
			[item[0], frappe.utils.esc(str(item[1]), "$ ")]
			for item in self.__dict__.copy().items()
		)

		if self.backup_includes:
			backup_info = ("Backing Up Tables: ", ", ".join(self.backup_includes))
		elif self.backup_excludes:
			backup_info = ("Skipping Tables: ", ", ".join(self.backup_excludes))

		if self.partial:
			print(''.join(backup_info), "\n")
			database_header_content.extend([
				f"Partial Backup of Frappe Site {frappe.local.site}",
				("Backup contains: " if self.backup_includes else "Backup excludes: ") + backup_info[1],
				"",
			])

		generated_header = "\n".join([f"-- {x}" for x in database_header_content]) + "\n"

		with gzip.open(args.backup_path_db, "wt") as f:
			f.write(generated_header)

		if self.db_type == "postgres":
			if self.backup_includes:
				args["include"] = " ".join(
					["--table='public.\"{0}\"'".format(table) for table in self.backup_includes]
				)
			elif self.backup_excludes:
				args["exclude"] = " ".join(
					["--exclude-table-data='public.\"{0}\"'".format(table) for table in self.backup_excludes]
				)

			cmd_string = (
				"{db_exc} postgres://{user}:{password}@{db_host}:{db_port}/{db_name}"
				" {include} {exclude} | {gzip} >> {backup_path_db}"
			)

		else:
			if self.backup_includes:
				args["include"] = " ".join(["'{0}'".format(x) for x in self.backup_includes])
			elif self.backup_excludes:
				args["exclude"] = " ".join(
					[
						"--ignore-table='{0}.{1}'".format(frappe.conf.db_name, table)
						for table in self.backup_excludes
					]
				)

			cmd_string = (
				"{db_exc} --single-transaction --quick --lock-tables=false -u {user}"
				" -p{password} {db_name} -h {db_host} -P {db_port} {include} {exclude}"
				" | {gzip} >> {backup_path_db}"
			)

		command = cmd_string.format(
			user=args.user,
			password=args.password,
			db_exc=db_exc,
			db_host=args.db_host,
			db_port=args.db_port,
			db_name=args.db_name,
			backup_path_db=args.backup_path_db,
			exclude=args.get("exclude", ""),
			include=args.get("include", ""),
			gzip=gzip_exc,
		)

		if self.verbose:
			print(command + "\n")

		frappe.utils.execute_in_shell(command, low_priority=True)

	def send_email(self):
		"""
		Sends the link to backup file located at erpnext/backups
		"""
		from frappe.email import get_system_managers

		recipient_list = get_system_managers()
		db_backup_url = get_url(
			os.path.join("backups", os.path.basename(self.backup_path_db))
		)
		files_backup_url = get_url(
			os.path.join("backups", os.path.basename(self.backup_path_files))
		)

		msg = """Hello,

Your backups are ready to be downloaded.

1. [Click here to download the database backup](%(db_backup_url)s)
2. [Click here to download the files backup](%(files_backup_url)s)

This link will be valid for 24 hours. A new backup will be available for
download only after 24 hours.""" % {
			"db_backup_url": db_backup_url,
			"files_backup_url": files_backup_url,
		}

		datetime_str = datetime.fromtimestamp(os.stat(self.backup_path_db).st_ctime)
		subject = (
			datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""
		)

		frappe.sendmail(recipients=recipient_list, msg=msg, subject=subject)
		return recipient_list


@frappe.whitelist()
def fetch_latest_backups(partial=False):
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
	database, public, private, config = odb.get_recent_backup(older_than=24 * 30, partial=partial)

	return {"database": database, "public": public, "private": private, "config": config}


def scheduled_backup(
	older_than=6,
	ignore_files=False,
	backup_path=None,
	backup_path_db=None,
	backup_path_files=None,
	backup_path_private_files=None,
	backup_path_conf=None,
	ignore_conf=False,
	include_doctypes="",
	exclude_doctypes="",
	compress=False,
	force=False,
	verbose=False,
):
	"""this function is called from scheduler
	deletes backups older than 7 days
	takes backup"""
	odb = new_backup(
		older_than=older_than,
		ignore_files=ignore_files,
		backup_path=backup_path,
		backup_path_db=backup_path_db,
		backup_path_files=backup_path_files,
		backup_path_private_files=backup_path_private_files,
		backup_path_conf=backup_path_conf,
		ignore_conf=ignore_conf,
		include_doctypes=include_doctypes,
		exclude_doctypes=exclude_doctypes,
		compress=compress,
		force=force,
		verbose=verbose,
	)
	return odb


def new_backup(
	older_than=6,
	ignore_files=False,
	backup_path=None,
	backup_path_db=None,
	backup_path_files=None,
	backup_path_private_files=None,
	backup_path_conf=None,
	ignore_conf=False,
	include_doctypes="",
	exclude_doctypes="",
	compress=False,
	force=False,
	verbose=False,
):
	delete_temp_backups()
	odb = BackupGenerator(
		frappe.conf.db_name,
		frappe.conf.db_name,
		frappe.conf.db_password,
		db_host=frappe.db.host,
		db_port=frappe.db.port,
		db_type=frappe.conf.db_type,
		backup_path=backup_path,
		backup_path_db=backup_path_db,
		backup_path_files=backup_path_files,
		backup_path_private_files=backup_path_private_files,
		backup_path_conf=backup_path_conf,
		ignore_conf=ignore_conf,
		include_doctypes=include_doctypes,
		exclude_doctypes=exclude_doctypes,
		verbose=verbose,
		compress_files=compress,
	)
	odb.get_backup(older_than, ignore_files, force=force)
	return odb


def delete_temp_backups(older_than=24):
	"""
	Cleans up the backup_link_path directory by deleting older files
	"""
	older_than = cint(frappe.conf.keep_backups_for_hours) or older_than
	backup_path = get_backup_path()
	if os.path.exists(backup_path):
		file_list = os.listdir(get_backup_path())
		for this_file in file_list:
			this_file_path = os.path.join(get_backup_path(), this_file)
			if is_file_old(this_file_path, older_than):
				os.remove(this_file_path)


def is_file_old(file_path, older_than=24):
	"""
	Checks if file exists and is older than specified hours
	Returns ->
	True: file does not exist or file is old
	False: file is new
	"""
	if os.path.isfile(file_path):
		from datetime import timedelta

		# Get timestamp of the file
		file_datetime = datetime.fromtimestamp(os.stat(file_path).st_ctime)
		if datetime.today() - file_datetime >= timedelta(hours=older_than):
			if _verbose:
				print(f"File {file_path} is older than {older_than} hours")
			return True
		else:
			if _verbose:
				print(f"File {file_path} is recent")
			return False
	else:
		if _verbose:
			print(f"File {file_path} does not exist")
		return True


def get_backup_path():
	backup_path = frappe.utils.get_site_path(conf.get("backup_path", "private/backups"))
	return backup_path


def backup(
	with_files=False,
	backup_path_db=None,
	backup_path_files=None,
	backup_path_private_files=None,
	backup_path_conf=None,
	quiet=False,
):
	"Backup"
	odb = scheduled_backup(
		ignore_files=not with_files,
		backup_path_db=backup_path_db,
		backup_path_files=backup_path_files,
		backup_path_private_files=backup_path_private_files,
		backup_path_conf=backup_path_conf,
		force=True,
	)
	return {
		"backup_path_db": odb.backup_path_db,
		"backup_path_files": odb.backup_path_files,
		"backup_path_private_files": odb.backup_path_private_files,
	}


if __name__ == "__main__":
	import sys

	cmd = sys.argv[1]

	db_type = "mariadb"
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
		odb = BackupGenerator(
			sys.argv[2],
			sys.argv[3],
			sys.argv[4],
			sys.argv[5] or "localhost",
			db_type=db_type,
			db_port=db_port,
		)
		is_file_old(odb.db_file_name)

	if cmd == "get_backup":
		odb = BackupGenerator(
			sys.argv[2],
			sys.argv[3],
			sys.argv[4],
			sys.argv[5] or "localhost",
			db_type=db_type,
			db_port=db_port,
		)
		odb.get_backup()

	if cmd == "take_dump":
		odb = BackupGenerator(
			sys.argv[2],
			sys.argv[3],
			sys.argv[4],
			sys.argv[5] or "localhost",
			db_type=db_type,
			db_port=db_port,
		)
		odb.take_dump()

	if cmd == "send_email":
		odb = BackupGenerator(
			sys.argv[2],
			sys.argv[3],
			sys.argv[4],
			sys.argv[5] or "localhost",
			db_type=db_type,
			db_port=db_port,
		)
		odb.send_email("abc.sql.gz")

	if cmd == "delete_temp_backups":
		delete_temp_backups()
