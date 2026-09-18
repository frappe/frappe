# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import contextlib

# imports - standard imports
import os
import shlex
import stat
import sys
import tempfile
from calendar import timegm
from collections.abc import Callable
from datetime import datetime
from functools import partial
from glob import glob
from shutil import copyfileobj, which

# imports - third party imports
import click
from cryptography.fernet import Fernet

# imports - module imports
import frappe
import frappe.utils
from frappe import _, conf
from frappe.utils import cint, format_bytes, get_file_size, get_url, now, now_datetime

# backup variable for backwards compatibility
verbose = False
compress = False
_verbose = verbose
base_tables = ["__Auth", "__global_search", "__UserSettings"]

BACKUP_ENCRYPTION_CONFIG_KEY = "backup_encryption_key"


def is_stream_path(path: str | None) -> bool:
	"""Return True if `path` is a pipe, device or socket rather than a regular file.

	A backup written to one of these is *streamed*: the consumer reads the bytes
	as they are produced - straight into object storage, a restore, or another
	host - instead of picking a finished file off disk. Point `--backup-path-db`
	and friends at a FIFO and the backup streams there; no flag needed.
	"""
	if not path:
		return False

	try:
		mode = os.stat(path).st_mode
	except OSError:
		return False

	return stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISSOCK(mode)


def _remove_if_exists(path: str) -> None:
	with contextlib.suppress(FileNotFoundError):
		os.remove(path)


class BackupGenerator:
	"""
	This class contains methods to perform On Demand Backup

	To initialize, specify (db_name, user, password, db_file_name=None, db_host="127.0.0.1")
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
		db_socket=None,
		db_host=None,
		db_port=None,
		db_type=None,
		backup_path_conf=None,
		ignore_conf=False,
		compress_files=False,
		include_doctypes="",
		exclude_doctypes="",
		verbose=False,
		old_backup_metadata=False,
		rollback_callback=None,
		destination=None,
	):
		global _verbose
		self.compress_files = compress_files or compress
		# A destination takes the bytes as they are produced; there is no local
		# file at any point, so every artifact is a stream by definition.
		self.destination = destination
		self.db_socket = db_socket
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
		self.old_backup_metadata = old_backup_metadata
		self.rollback_callback = rollback_callback

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

			for file_path in {
				self.backup_path_files,
				self.backup_path_db,
				self.backup_path_private_files,
				self.backup_path_conf,
			}:
				if file_path:
					dir = os.path.dirname(file_path)
					os.makedirs(dir, exist_ok=True)

	def is_streamed(self, path: str | None) -> bool:
		"""Whether `path` receives a stream of bytes instead of a file on disk."""
		if not path:
			return False
		return bool(self.destination) or is_stream_path(path)

	@property
	def streaming(self) -> bool:
		"""Whether any artifact of this backup is being streamed."""
		if self.destination:
			return True
		return any(
			self.is_streamed(path)
			for path in (
				self.backup_path_db,
				self.backup_path_conf,
				self.backup_path_files,
				self.backup_path_private_files,
			)
		)

	@contextlib.contextmanager
	def open_artifact(self, path: str):
		"""Open `path` once, for the whole artifact, and yield its descriptor.

		Every byte of an artifact leaves through this one descriptor. On disk that
		is merely tidy; on a stream it is the contract. A reader sees EOF the
		moment the last writer closes a pipe, so an artifact written in two
		sessions - a header, then a dump appended to it - would reach that reader
		truncated at the first close, and the second writer would go on to block
		on a pipe nobody is draining any more.

		Opening a pipe for writing blocks until a reader arrives, which is also
		what paces the backup to the speed the consumer can take it.
		"""
		if self.destination:
			# The path only names the artifact now - the bytes go to the
			# destination, and the descriptor is a pipe feeding its uploader.
			with self.destination.stream(os.path.basename(path)) as fd:
				yield fd
			return

		flags = os.O_WRONLY | os.O_CREAT
		if not self.is_streamed(path):
			# Truncation is a no-op on a pipe and unwanted on a device.
			flags |= os.O_TRUNC

		fd = os.open(path, flags, 0o666)
		try:
			yield fd
		finally:
			os.close(fd)

	@contextlib.contextmanager
	def encryption_filter(self):
		"""Yield a pipeline segment that encrypts stdin, or "" when encryption is off.

		Encrypting inline - instead of rewriting a finished file in place - is what
		makes encrypted backups streamable at all, and it keeps the plaintext from
		ever reaching disk.
		"""
		if not frappe.get_system_settings("encrypt_backup"):
			yield ""
			return

		gpg_exc = which("gpg")
		if not gpg_exc:
			click.secho("Please install `gpg` and ensure its available in your PATH", fg="red")
			sys.exit(1)

		# The passphrase travels via a 0600 file rather than an argument, so it
		# never shows up in the process table.
		with tempfile.NamedTemporaryFile("w", prefix="backup-passphrase-") as passphrase_file:
			passphrase_file.write(get_or_generate_backup_encryption_key())
			passphrase_file.flush()
			yield (
				f" | {shlex.quote(gpg_exc)} --batch --yes --pinentry-mode loopback"
				f" --passphrase-file {shlex.quote(passphrase_file.name)} --symmetric"
			)

	def gzip_executable(self) -> str:
		gzip_exc = which("gzip")
		if not gzip_exc:
			frappe.throw(
				_("gzip not found in PATH! This is required to take a backup."), exc=frappe.ExecutableNotFound
			)
		return gzip_exc

	def _set_existing_tables(self):
		"""Ensure self._existing_tables is set."""
		if not hasattr(self, "_existing_tables"):
			self._existing_tables = frappe.db.get_tables()

	def setup_backup_tables(self):
		"""Set self.backup_includes, self.backup_excludes based on include_doctypes, exclude_doctypes"""
		self._set_existing_tables()

		self.backup_includes = _get_tables(self.include_doctypes.strip().split(","), self._existing_tables)
		self.backup_excludes = _get_tables(self.exclude_doctypes.strip().split(","), self._existing_tables)

		self.set_backup_tables_from_config()
		self.partial = (self.backup_includes or self.backup_excludes) and not self.ignore_conf

	def set_backup_tables_from_config(self):
		"""Set self.backup_includes, self.backup_excludes based on site config.

		Uses `strict=False` when resolving config entries: stale doctype
		names (e.g. from an uninstalled app) log a warning and are skipped
		rather than aborting the scheduled backup. If the config resolves
		to entirely-unknown doctypes, `_get_tables` takes a full backup with
		warning message.
		"""
		if self.ignore_conf:
			return

		backup_conf = frappe.conf.get("backup", {})
		self._set_existing_tables()
		if not self.backup_includes:
			if specified_tables := _get_tables(
				backup_conf.get("includes", []), self._existing_tables, strict=False
			):
				self.backup_includes = specified_tables + base_tables
			else:
				self.backup_includes = []

		if not self.backup_excludes:
			self.backup_excludes = _get_tables(
				backup_conf.get("excludes", []), self._existing_tables, strict=False
			)

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
		# If not Take Dump. A streamed artifact can never be reused: the consumer
		# is waiting on this run's bytes, not on a path to an older file.
		if not (force or self.streaming):
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

		if not (
			self.backup_path_conf
			and self.backup_path_db
			and self.backup_path_files
			and self.backup_path_private_files
		):
			self.set_backup_file_name()

		if not (last_db and last_file and last_private_file and site_config_backup_path):
			self.delete_if_step_fails(self.take_dump, self.backup_path_db)
			self.delete_if_step_fails(self.copy_site_config, self.backup_path_conf)
			if not ignore_files:
				self.delete_if_step_fails(
					self.backup_files, self.backup_path_files, self.backup_path_private_files
				)

		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db
			self.backup_path_private_files = last_private_file
			self.backup_path_conf = site_config_backup_path

	def set_backup_file_name(self):
		partial = "-partial" if self.partial else ""
		ext = "tgz" if self.compress_files else "tar"
		enc = "-enc" if frappe.get_system_settings("encrypt_backup") else ""
		self.todays_date = now_datetime().strftime("%Y%m%d_%H%M%S")

		for_conf = f"{self.todays_date}-{self.site_slug}-site_config_backup{enc}.json"
		for_db = f"{self.todays_date}-{self.site_slug}{partial}-database{enc}.sql.gz"
		for_public_files = f"{self.todays_date}-{self.site_slug}-files{enc}.{ext}"
		for_private_files = f"{self.todays_date}-{self.site_slug}-private-files{enc}.{ext}"
		backup_path = self.backup_path or get_backup_path()

		if not self.backup_path_conf:
			self.backup_path_conf = os.path.join(backup_path, for_conf)
		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def backup_encryption(self):
		"""
		Encrypt all the backups created using gpg.

		Deprecated: backups are now encrypted as they are written (see
		:meth:`encryption_filter`), which keeps the plaintext off disk and works on
		a stream. This rewrites finished files in place and only ever worked on
		regular files; it is kept for callers outside the framework.
		"""
		click.secho(
			"BackupGenerator.backup_encryption has been deprecated - backups taken by"
			" BackupGenerator are already encrypted in place while they are written",
			fg="yellow",
		)
		if which("gpg") is None:
			click.secho("Please install `gpg` and ensure its available in your PATH", fg="red")
			sys.exit(1)
		paths = (self.backup_path_db, self.backup_path_files, self.backup_path_private_files)
		for path in paths:
			if os.path.exists(path):
				cmd_string = "gpg --yes --passphrase {passphrase} --pinentry-mode loopback -c {filelocation}"
				try:
					command = cmd_string.format(
						passphrase=get_or_generate_backup_encryption_key(),
						filelocation=path,
					)

					frappe.utils.execute_in_shell(command)
					os.rename(path + ".gpg", path)

				except Exception as err:
					print(err)
					click.secho(
						"Error occurred during encryption. Files are stored without encryption.", fg="red"
					)

	def get_recent_backup(self, older_than, partial=False):
		backup_path = get_backup_path()
		separator = suffix = ""
		if partial:
			separator = "*"

		if frappe.get_system_settings("encrypt_backup"):
			suffix = "-enc"

		file_type_slugs = {
			"database": f"*-{{}}-{separator}database{suffix}.sql.gz",
			"public": f"*-{{}}-files{suffix}.tar",
			"private": f"*-{{}}-private-files{suffix}.tar",
			"config": f"*-{{}}-site_config_backup{suffix}.json",
		}

		def backup_time(file_path):
			file_name = file_path.split(os.sep)[-1]
			file_timestamp = file_name.split("-", 1)[0]
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

		latest_backups = {file_type: get_latest(pattern) for file_type, pattern in file_type_slugs.items()}

		recent_backups = {file_type: old_enough(file_name) for file_type, file_name in latest_backups.items()}

		return (
			recent_backups.get("database"),
			recent_backups.get("public"),
			recent_backups.get("private"),
			recent_backups.get("config"),
		)

	def zip_files(self):
		# For backwards compatibility - pre v13
		click.secho(
			"BackupGenerator.zip_files has been deprecated in favour of BackupGenerator.backup_files",
			fg="yellow",
		)
		return self.backup_files()

	def get_summary(self):
		summary = {
			"config": {
				"path": self.artifact_location(self.backup_path_conf),
				"size": self.artifact_size(self.backup_path_conf),
			},
			"database": {
				"path": self.artifact_location(self.backup_path_db),
				"size": self.artifact_size(self.backup_path_db),
			},
		}

		if self.artifact_exists(self.backup_path_files) and self.artifact_exists(
			self.backup_path_private_files
		):
			summary.update(
				{
					"public": {
						"path": self.artifact_location(self.backup_path_files),
						"size": self.artifact_size(self.backup_path_files),
					},
					"private": {
						"path": self.artifact_location(self.backup_path_private_files),
						"size": self.artifact_size(self.backup_path_private_files),
					},
				}
			)

		return summary

	def artifact_exists(self, path: str) -> bool:
		if self.destination:
			return self.destination.size_of(os.path.basename(path)) is not None
		return os.path.exists(path)

	def artifact_location(self, path: str) -> str:
		if self.destination:
			return self.destination.url_for(os.path.basename(path))
		return path

	def artifact_size(self, path: str) -> str:
		if self.destination:
			uploaded = self.destination.size_of(os.path.basename(path))
			return format_bytes(uploaded) if uploaded is not None else "not uploaded"
		# A pipe holds nothing, so there is no size to report - whoever drained it
		# is the one who knows how many bytes came out.
		if self.is_streamed(path):
			return "streamed"
		return get_file_size(path, format=True)

	def print_summary(self):
		backup_summary = self.get_summary()
		print(f"Backup Summary for {frappe.local.site} at {now()}")

		title = max(len(x) for x in backup_summary)
		path = max(len(x["path"]) for x in backup_summary.values())

		for _type, info in backup_summary.items():
			template = f"{{0:{title}}}: {{1:{path}}} {{2}}"
			location = info["path"] if self.destination else os.path.abspath(info["path"])
			print(template.format(_type.title(), location, info["size"]))

	def backup_files(self):
		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = self.backup_path_files if folder == "public" else self.backup_path_private_files

			# tar writes to stdout rather than opening the destination itself, so
			# the archive, the optional compression and the optional encryption are
			# one pipeline landing on one descriptor - see open_artifact().
			command = f"tar -cf - {shlex.quote(files_path)}"
			if self.compress_files:
				command += f" | {shlex.quote(self.gzip_executable())}"

			with self.encryption_filter() as encrypt, self.open_artifact(backup_path) as fd:
				try:
					frappe.utils.execute_in_shell(
						f"set -e -o pipefail; {command}{encrypt}",
						verbose=self.verbose,
						low_priority=True,
						check_exit_code=True,
						stdout=fd,
					)
				except frappe.CommandFailedError as e:
					if e.err and "file changed as we read it" in e.err:
						click.secho(
							"Ignoring `tar: file changed as we read it` to prevent backup failure",
							fg="red",
						)
					else:
						raise e

	def copy_site_config(self):
		"""Copy site_config.json to the config artifact.

		Left unencrypted deliberately, matching long-standing behaviour: only the
		database and the two file archives go through `encryption_filter`, even
		though `set_backup_file_name` stamps `-enc` on this artifact's name too.
		Note that site_config.json carries `backup_encryption_key`, so this copy
		exposes the key that decrypts the other artifacts.
		"""
		site_config_path = os.path.join(frappe.get_site_path(), "site_config.json")

		with self.open_artifact(self.backup_path_conf) as fd:
			# dup the descriptor so closing the buffered wrapper doesn't close the
			# artifact out from under open_artifact()
			with open(site_config_path, "rb") as source, os.fdopen(os.dup(fd), "wb") as target:
				copyfileobj(source, target)

	def take_dump(self):
		"""Write the database dump to `self.backup_path_db`.

		The metadata header, the dump and (when enabled) encryption form a single
		pipeline writing to a single descriptor, so the artifact is as valid on a
		pipe as it is on disk - see :meth:`open_artifact`.
		"""
		command = self.get_dump_command()

		if self.verbose:
			printable = command.replace(shlex.quote(self.password), "*" * 10) if self.password else command
			print(printable + "\n")

		with self.encryption_filter() as encrypt, self.open_artifact(self.backup_path_db) as fd:
			frappe.utils.execute_in_shell(
				f"set -e -o pipefail; {command}{encrypt}",
				verbose=self.verbose,
				low_priority=True,
				check_exit_code=True,
				stdout=fd,
			)

	def get_dump_command(self) -> str:
		"""Return a shell pipeline that writes the compressed database dump to stdout."""
		gzip_exc = self.gzip_executable()

		if self.db_type == "sqlite":
			db_path = os.path.join(frappe.get_site_path(), "db", f"{self.db_name}.db")
			return f"{shlex.quote(gzip_exc)} -c -- {shlex.quote(db_path)}"

		from frappe.database import get_command
		from frappe.utils.change_log import get_app_branch

		if self.old_backup_metadata:
			database_header_content = [
				f"Backup generated by Frappe {frappe.__version__} on branch {get_app_branch('frappe') or 'N/A'}",
				"",
			]
		else:
			database_header_content = [
				"begin frappe metadata",
				"[frappe]",
				f"version = {frappe.__version__}",
				f"branch = {get_app_branch('frappe') or 'N/A'}",
				"end frappe metadata",
				"",
			]

		if self.backup_includes:
			backup_info = ("Backing Up Tables: ", ", ".join(self.backup_includes))
		elif self.backup_excludes:
			backup_info = ("Skipping Tables: ", ", ".join(self.backup_excludes))

		if self.partial:
			if self.verbose:
				print("".join(backup_info), "\n")
			database_header_content.extend(
				[
					f"Partial Backup of Frappe Site {frappe.local.site}",
					("Backup contains: " if self.backup_includes else "Backup excludes: ") + backup_info[1],
					"",
				]
			)

		generated_header = "\n".join(f"-- {x}" for x in database_header_content) + "\n"

		extra = []
		if self.db_type == "mariadb":
			if self.backup_includes:
				extra.extend(self.backup_includes)
			elif self.backup_excludes:
				extra.extend([f"--ignore-table={self.db_name}.{table}" for table in self.backup_excludes])

		elif self.db_type == "postgres":
			if self.backup_includes:
				extra.extend([f'--table=public."{table}"' for table in self.backup_includes])
			elif self.backup_excludes:
				extra.extend([f'--exclude-table-data=public."{table}"' for table in self.backup_excludes])

		bin, args, bin_name = get_command(
			socket=self.db_socket,
			host=self.db_host,
			port=self.db_port,
			user=self.user,
			password=self.password,
			db_name=self.db_name,
			extra=extra,
			dump=True,
		)
		if not bin:
			frappe.throw(
				_("{} not found in PATH! This is required to take a backup.").format(bin_name),
				exc=frappe.ExecutableNotFound,
			)

		# The header is its own gzip member ahead of the dump's. gzip members
		# concatenate, so a reader - or `gunzip` - sees one continuous file, while
		# the writer never has to reopen the destination to append.
		return (
			f"{{ printf -- '%s' {shlex.quote(generated_header)} | {shlex.quote(gzip_exc)};"
			f" {shlex.quote(bin)} {shlex.join(args)} | {shlex.quote(gzip_exc)}; }}"
		)

	def send_email(self):
		"""
		Sends the link to backup file located at erpnext/backups
		"""
		from frappe.email import get_system_managers

		recipient_list = get_system_managers()
		db_backup_url = get_url(os.path.join("backups", os.path.basename(self.backup_path_db)))
		files_backup_url = get_url(os.path.join("backups", os.path.basename(self.backup_path_files)))

		msg = f"""Hello,

Your backups are ready to be downloaded.

1. [Click here to download the database backup]({db_backup_url})
2. [Click here to download the files backup]({files_backup_url})

This link will be valid for 24 hours. A new backup will be available for
download only after 24 hours."""

		datetime_str = datetime.fromtimestamp(os.stat(self.backup_path_db).st_ctime)
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""

		frappe.sendmail(recipients=recipient_list, message=msg, subject=subject)
		return recipient_list

	def add_to_rollback(self, func: Callable) -> None:
		"""
		Adds the given callable to the rollback CallbackManager stack

		:param func: The callable to add to the rollback stack
		:return: Nothing
		"""
		if self.rollback_callback:
			self.rollback_callback.add(func)

	def delete_if_step_fails(self, step: Callable, *paths: str):
		"""
		Deletes the given path if the given step fails

		:param step: The step to execute
		:param paths: The paths to delete
		:return: Nothing
		"""
		# A streamed artifact leaves no file to clean up, and the pipe belongs to
		# whoever created it - deleting it would only break the consumer. This is
		# what lets a caller hand us a FIFO and keep it for the whole backup.
		paths = [path for path in paths if path and not self.is_streamed(path)]

		try:
			step()
		except Exception as e:
			for path in paths:
				_remove_if_exists(path)
			raise e
		for path in paths:
			# partial() binds this iteration's path; a closure over the loop
			# variable would roll back the last path once per registered callback
			self.add_to_rollback(partial(_remove_if_exists, path))


def _get_tables(doctypes: list[str], existing_tables: list[str], strict: bool = True) -> list[str]:
	"""Return tables for the given doctypes.

	`strict=True` (default; CLI / programmatic direct callers): raise
	    ValidationError if any input doctype doesn't resolve. Caller can
	    fix the input immediately.

	`strict=False` (site-config-driven paths): scheduled backups shouldn't
	    break on stale config left over from an app uninstall / doctype
	    rename, but we should also not silently take the wrong backup.
	    Two sub-cases, both warn explicitly so the admin sees what
	    happened:
	      - partial-resolve: some entries valid, some not → continue with
	        the valid subset, warn about the missing ones
	      - all-invalid:  no entries valid → return empty list (flows
	        through as a full backup) and warn LOUDLY that a full backup
	        is being taken as a fallback.
	"""
	tables = []
	missing = []
	for doctype in doctypes:
		doctype = (doctype or "").strip()
		if not doctype:
			continue
		table = frappe.utils.get_table_name(doctype)
		if table in existing_tables:
			tables.append(table)
		else:
			missing.append(doctype)

	if missing:
		if strict:
			frappe.throw(
				_(
					"Backup requested for unknown DocType(s): {0}. "
					"Check for typos or use the exact DocType name (case-sensitive). "
					"Aborting to avoid taking a full backup instead of the requested subset."
				).format(", ".join(missing)),
				exc=frappe.ValidationError,
			)
		elif not tables:
			# All entries invalid. Fall back to full backup rather than
			# aborting the scheduled run — but warn LOUDLY so admin knows
			# the requested subset couldn't be produced.
			frappe.logger().warning(
				f"Backup: site config backup.includes/excludes references only "
				f"unknown DocType(s): {', '.join(missing)}. "
				f"Falling back to FULL BACKUP — no partial subset could be produced. "
				f"Fix the site config entries to restore partial backup behavior."
			)
		else:
			# Partial resolve — tolerated maintenance case. Warn about
			# skipped entries so admin knows the backup no longer covers
			# those doctypes.
			frappe.logger().warning(
				f"Backup: skipping unknown DocType(s) from site config: {', '.join(missing)}. "
				f"Continuing with {len(tables)} valid entries — the resulting backup "
				f"will NOT contain data for the skipped doctypes."
			)

	return tables


@frappe.whitelist()
def fetch_latest_backups(partial: bool = False) -> dict:
	"""Fetch paths of the latest backup taken in the last 30 days.

	Note: Only for System Managers

	Return:
	        dict: relative Backup Paths
	"""
	frappe.only_for("System Manager")
	odb = BackupGenerator(
		frappe.conf.db_name,
		frappe.conf.db_user,
		frappe.conf.db_password,
		db_socket=frappe.conf.db_socket,
		db_host=frappe.conf.db_host,
		db_port=frappe.conf.db_port,
		db_type=frappe.conf.db_type,
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
	old_backup_metadata=False,
	rollback_callback=None,
	destination=None,
):
	"""this function is called from scheduler
	deletes backups older than 7 days
	takes backup"""
	return new_backup(
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
		old_backup_metadata=old_backup_metadata,
		rollback_callback=rollback_callback,
		destination=destination,
	)


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
	old_backup_metadata=False,
	rollback_callback=None,
	destination=None,
):
	delete_temp_backups()
	odb = BackupGenerator(
		frappe.conf.db_name,
		frappe.conf.db_user,
		frappe.conf.db_password,
		db_socket=frappe.conf.db_socket,
		db_host=frappe.conf.db_host,
		db_port=frappe.conf.db_port,
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
		old_backup_metadata=old_backup_metadata,
		rollback_callback=rollback_callback,
		destination=destination,
	)
	odb.get_backup(older_than, ignore_files, force=force)
	return odb


def delete_temp_backups(older_than=23):
	"""
	Cleans up the backup_link_path directory by deleting older files
	"""
	older_than = cint(frappe.conf.keep_backups_for_hours) or older_than
	backup_path = get_backup_path()
	if os.path.exists(backup_path):
		file_list = os.listdir(get_backup_path())
		for this_file in file_list:
			this_file_path = os.path.join(get_backup_path(), this_file)
			# Only regular files are ours to clean up: a FIFO here is a consumer
			# waiting on a streamed backup, not a leftover.
			if os.path.isfile(this_file_path) and is_file_old(this_file_path, older_than):
				os.remove(this_file_path)


def is_file_old(file_path, older_than=24) -> bool:
	"""
	Return True if the path is older than specified hours. Also treat non-existent paths as "old".
	"""
	if os.path.exists(file_path):
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
	return frappe.utils.get_site_path(conf.get("backup_path", "private/backups"))


@frappe.whitelist()
def get_backup_encryption_key():
	frappe.only_for("System Manager")
	return get_or_generate_backup_encryption_key()


def get_or_generate_backup_encryption_key():
	from frappe.installer import update_site_config

	key = frappe.conf.get(BACKUP_ENCRYPTION_CONFIG_KEY)
	if key:
		return key

	key = Fernet.generate_key().decode()
	update_site_config(BACKUP_ENCRYPTION_CONFIG_KEY, key)

	return key


@contextlib.contextmanager
def decrypt_backup(file_path: str, passphrase: str):
	if which("gpg") is None:
		click.secho("Please install `gpg` and ensure its available in your PATH", fg="red")
		sys.exit(1)
	if not os.path.exists(file_path):
		print("Invalid path: ", file_path)
		return
	else:
		file_path_with_ext = file_path + ".gpg"
		os.rename(file_path, file_path_with_ext)

		cmd_string = "gpg --yes --passphrase {passphrase} --pinentry-mode loopback -o {decrypted_file} -d {file_location}"
		command = cmd_string.format(
			passphrase=passphrase,
			file_location=file_path_with_ext,
			decrypted_file=file_path,
		)
	frappe.utils.execute_in_shell(command)
	try:
		yield
	finally:
		if os.path.exists(file_path_with_ext):
			if os.path.exists(file_path):
				os.remove(file_path)
			if os.path.exists(file_path.rstrip(".gz")):
				os.remove(file_path.rstrip(".gz"))
			os.rename(file_path_with_ext, file_path)


def backup(
	with_files=False,
	backup_path_db=None,
	backup_path_files=None,
	backup_path_private_files=None,
	backup_path_conf=None,
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
