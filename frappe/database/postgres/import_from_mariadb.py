# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Convert a MariaDB site backup into a PostgreSQL database using pgloader.

pgloader reads from a live MySQL/MariaDB server (not a `.sql` dump) and does not run on
ARM/Apple Silicon, so conversion needs a reachable MariaDB server to stage the dump and an
x86_64 host. The pgloader run reproduces Frappe's PostgreSQL column types; JSON fields
(longtext in MariaDB) land as text and are reconciled to native `json` by the `bench
migrate` that follows the restore.

Very large schemas can exceed PostgreSQL's `max_locks_per_transaction` while pgloader
builds them ("out of shared memory"); if pgloader reports it, raise that setting in
postgresql.conf and restart the server (it's postmaster-level, so it can't be set per run).
"""

import os
import platform
import shlex
import tempfile
from shutil import which
from urllib.parse import quote

import frappe
from frappe.utils import execute_in_shell

# MariaDB type -> PostgreSQL type rules that reproduce the columns Frappe itself creates.
TYPE_CASTS = (
	'type datetime to "timestamp without time zone" drop typemod using zero-dates-to-null',
	"type date drop not null using zero-dates-to-null",
	'type time to "time without time zone" drop typemod',
	"type tinyint to smallint drop typemod",
	"type int to integer drop typemod",
	"type bigint to bigint drop typemod",
	"type decimal to numeric keep typemod",
	"type varchar to varchar keep typemod",
	"type text to text",
	"type tinytext to text",
	"type mediumtext to text",
	"type longtext to text",
)

# Conversion options for the restore hook. Module globals (not frappe.flags) because the
# frappe.init() inside _new_site() resets frappe.local before the hook runs.
_staging_mariadb: dict | None = None
# MB for pgloader's SBCL heap; None leaves pgloader's own default. Raise for very large dumps.
_dynamic_space_mb: int | None = None


def set_staging_mariadb(conn: dict | None, dynamic_space_mb: int | None = None) -> None:
	global _staging_mariadb, _dynamic_space_mb
	_staging_mariadb = conn
	# Assign unconditionally so a later call without a heap size resets the previous one.
	_dynamic_space_mb = dynamic_space_mb


def assert_conversion_supported() -> None:
	"""Fail early unless pgloader can run here (x86_64 with pgloader installed).

	Raises exception classes directly (not frappe.throw) so it works in the standalone
	`bench convert-mariadb-backup` command, which runs without an initialised frappe.
	"""
	if platform.machine().lower() in ("arm64", "aarch64"):
		raise frappe.ValidationError(
			"Converting MariaDB backups to PostgreSQL needs pgloader, which does not run on "
			"ARM/Apple Silicon. Run the conversion on an x86_64 host."
		)
	if not which("pgloader"):
		raise frappe.ExecutableNotFound(
			"`pgloader` not found in PATH. It is required to convert MariaDB backups to "
			"PostgreSQL; install it (e.g. `apt-get install pgloader`) and retry."
		)


def _uri(scheme: str, conn: dict, db_name: str, include_password: bool = True) -> str:
	user = quote(conn["user"], safe="")
	password = quote(conn.get("password") or "", safe="") if include_password else ""
	credentials = f"{user}:{password}@" if password else f"{user}@"
	return f"{scheme}://{credentials}{conn['host']}:{conn['port']}/{db_name}"


def _mysql_identifier(name: str) -> str:
	"""Backtick-quote a MySQL identifier so hyphens/reserved words stay valid in DDL."""
	return "`" + name.replace("`", "``") + "`"


def build_pgloader_command(source_db: str, mariadb: dict, postgres: dict, target_db: str) -> str:
	"""Return the pgloader load-file contents for a MariaDB -> PostgreSQL data copy.

	`create no indexes`: the post-restore `bench migrate` recreates the secondary indexes
	under Frappe's own names, so letting pgloader also copy them (under its generated
	names) would leave two indexes per column. The table's primary key is created with the
	table, not as a secondary index, so it is unaffected.
	"""
	casts = ",\n      ".join(TYPE_CASTS)
	return f"""LOAD DATABASE
     FROM      {_uri("mysql", mariadb, source_db)}
     INTO      {_uri("postgresql", postgres, target_db)}

 WITH include drop, create tables, create no indexes, reset sequences,
      quote identifiers,
      workers = 8, concurrency = 1,
      batch rows = 5000, prefetch rows = 10000

 SET PostgreSQL PARAMETERS
      maintenance_work_mem to '512MB',
      work_mem to '128MB'

 CAST {casts}

 ALTER SCHEMA '{source_db}' RENAME TO 'public'
;
"""


class MariaDBToPostgres:
	"""Populate an existing PostgreSQL database from a MariaDB site dump.

	The target PostgreSQL database must already exist; pgloader creates the schema and
	copies the data into it. JSON fields land as text (MariaDB stores them as longtext);
	the subsequent `bench migrate` reconciles them to native json.
	"""

	def __init__(
		self,
		source_dump,
		mariadb,
		postgres,
		staging_db=None,
		verbose=False,
		keep_staging=False,
		dynamic_space_mb=None,
	):
		self.source_dump = source_dump
		self.mariadb = mariadb
		self.postgres = postgres
		self.staging_db = staging_db or f"_pgload_{frappe.generate_hash(length=10)}"
		self.verbose = verbose
		self.keep_staging = keep_staging
		self.dynamic_space_mb = dynamic_space_mb

	def run(self):
		assert_conversion_supported()
		self._validate_source()
		try:
			self._stage_dump_in_mariadb()
			self._run_pgloader()
		finally:
			if not self.keep_staging:
				self._drop_staging()

	def _validate_source(self):
		from frappe.installer import get_dump_db_type, is_partial, validate_database_sql

		validate_database_sql(self.source_dump)
		if get_dump_db_type(self.source_dump) != "mariadb":
			raise frappe.ValidationError(f"{self.source_dump} is not a MariaDB database dump.")
		if is_partial(self.source_dump):
			raise frappe.ValidationError("Cannot convert a partial backup to PostgreSQL.")

	def _sh(self, command: str):
		execute_in_shell(command, check_exit_code=True, verbose=self.verbose)

	def _mysql(self) -> str:
		# Quote every value (shell injection) and pass the password via MYSQL_PWD so it
		# never reaches the process list.
		args = [
			"mysql",
			f"--host={self.mariadb['host']}",
			f"--port={self.mariadb['port']}",
			f"--user={self.mariadb['user']}",
		]
		command = " ".join(shlex.quote(arg) for arg in args)
		if self.mariadb.get("password"):
			command = f"MYSQL_PWD={shlex.quote(self.mariadb['password'])} {command}"
		return command

	def _stage_dump_in_mariadb(self):
		mysql = self._mysql()
		staging = _mysql_identifier(self.staging_db)
		create = (
			f"DROP DATABASE IF EXISTS {staging}; "
			f"CREATE DATABASE {staging} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
		)
		self._sh(f"{mysql} -e {shlex.quote(create)}")

		dump = shlex.quote(self.source_dump)
		decompress = f"gzip -dc {dump}" if self.source_dump.endswith(".gz") else f"cat {dump}"
		# Strip the MariaDB sandbox-mode line that older clients choke on (as bench restore does).
		self._sh(
			f"set -o pipefail; {decompress} | sed '/\\/\\*M!999999/d' | {mysql} {shlex.quote(self.staging_db)}"
		)

	def _run_pgloader(self):
		content = build_pgloader_command(
			self.staging_db, self.mariadb, self.postgres, self.postgres["db_name"]
		)
		with tempfile.NamedTemporaryFile("w", suffix=".load", delete=False) as load_file:
			load_file.write(content)
			load_file.flush()
			path = load_file.name
		try:
			space = f"--dynamic-space-size {self.dynamic_space_mb} " if self.dynamic_space_mb else ""
			self._sh(f"pgloader {space}{shlex.quote(path)}")
		finally:
			os.unlink(path)

	def _drop_staging(self):
		drop = f"DROP DATABASE IF EXISTS {_mysql_identifier(self.staging_db)};"
		self._sh(f"{self._mysql()} -e {shlex.quote(drop)}")


def _connect(conn: dict, db_name: str):
	import psycopg2

	connection = psycopg2.connect(
		host=conn["host"],
		port=conn["port"],
		dbname=db_name,
		user=conn["user"],
		password=conn.get("password") or "",
	)
	connection.autocommit = True
	return connection


def import_mariadb_dump(source_dump: str, verbose: bool = False):
	"""Restore hook: convert a MariaDB dump into the current PostgreSQL site's database."""
	if not _staging_mariadb:
		raise frappe.ValidationError(
			"Restoring a MariaDB backup onto a PostgreSQL site needs the source MariaDB "
			"connection. Pass --source-mariadb-host / --source-mariadb-root-username / "
			"--source-mariadb-root-password to bench restore."
		)
	postgres = {
		"host": frappe.conf.db_host or "localhost",
		"port": frappe.conf.db_port or 5432,
		"user": frappe.conf.db_user,
		"password": frappe.conf.db_password,
		"db_name": frappe.conf.db_name,
	}
	MariaDBToPostgres(
		source_dump, _staging_mariadb, postgres, verbose=verbose, dynamic_space_mb=_dynamic_space_mb
	).run()


def convert_backup_to_postgres(
	source_dump,
	output,
	mariadb,
	postgres_root,
	verbose=False,
	dynamic_space_mb=None,
) -> str:
	"""Convert a MariaDB backup file into a restorable PostgreSQL backup file.

	Loads into a throwaway PostgreSQL database, then dumps it out as a Frappe-style
	gzipped backup. `postgres_root` must be a superuser able to create databases.
	"""
	assert_conversion_supported()
	scratch_db = f"_pgconv_{frappe.generate_hash(length=10)}"
	_admin_sql(postgres_root, f'CREATE DATABASE "{scratch_db}"')
	try:
		target = {**postgres_root, "db_name": scratch_db}
		MariaDBToPostgres(
			source_dump, mariadb, target, verbose=verbose, dynamic_space_mb=dynamic_space_mb
		).run()
		_pg_dump_to_file(target, output, source_dump)
	finally:
		_admin_sql(postgres_root, f'DROP DATABASE IF EXISTS "{scratch_db}"')
	return output


def _admin_sql(postgres_root: dict, statement: str):
	connection = _connect(postgres_root, "postgres")
	try:
		with connection.cursor() as cursor:
			cursor.execute(statement)
	finally:
		connection.close()


def _pg_dump_to_file(target: dict, output: str, source_dump: str):
	header = _frappe_metadata_header(source_dump)
	# Password via PGPASSWORD env, not the URI, so it stays out of the process list.
	uri = _uri("postgresql", target, target["db_name"], include_password=False)
	pg_env = f"PGPASSWORD={shlex.quote(target['password'])} " if target.get("password") else ""
	with tempfile.NamedTemporaryFile("w", suffix=".hdr", delete=False) as header_file:
		header_file.write(header)
		header_file.flush()
		header_path = header_file.name
	try:
		# A gzip file may hold multiple members, so the header and dump concatenate cleanly.
		execute_in_shell(
			f"set -o pipefail; gzip -c {shlex.quote(header_path)} > {shlex.quote(output)}; "
			f"{pg_env}pg_dump --no-owner --no-acl {shlex.quote(uri)} | gzip >> {shlex.quote(output)}",
			check_exit_code=True,
		)
	finally:
		os.unlink(header_path)


def _frappe_metadata_header(source_dump: str) -> str:
	"""Carry over the `-- begin/end frappe metadata` block from the source dump."""
	from frappe.installer import get_db_dump_header

	header = get_db_dump_header(source_dump, file_bytes=512)
	start = header.find("-- begin frappe metadata")
	end = header.find("-- end frappe metadata")
	if start != -1 and end != -1:
		return header[start : end + len("-- end frappe metadata")] + "\n"
	return "-- begin frappe metadata\n-- end frappe metadata\n"
