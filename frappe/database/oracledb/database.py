import oracledb

import frappe
from frappe.database.database import Database
from frappe.database.db_manager import DbManager
from frappe.database.utils import EmptyQueryValues, LazyDecode
from frappe.utils import cstr, get_table_name, get_datetime, UnicodeWithAttrs


class OracleDbManager(DbManager):
	@staticmethod
	def restore_database(verbose: bool, target: str, source: str, user: str,
						 password: str, service_name: str) -> None:

		"""
		Function to restore the given SQL file to the target database.
		:param target: The database to restore to.
		:param source: The SQL dump to restore
		:param user: The database username
		:param password: The database password
		:return: Nothing
		"""

		import shlex
		from shutil import which

		from frappe.database import get_command
		from frappe.utils import execute_in_shell

		# Ensure that the entire process fails if any part of the pipeline fails
		command: list[str] = ["set -o pipefail;"]

		# Handle gzipped backups
		if source.endswith(".gz"):
			if gzip := which("gzip"):
				command.extend([gzip, "-cd", source, "|"])
			else:
				raise Exception("`gzip` not installed")
		else:
			command.extend(["cat", source, "|"])

		# Newer versions of MariaDB add in a line that'll break on older versions, so remove it
		command.extend(["sed", r"'/\/\*M\{0,1\}!999999\\- enable the sandbox mode \*\//d'", "|"])

		# Generate the restore command
		bin, args, bin_name = get_command(
			socket=frappe.conf.db_socket,
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=user,
			password=password,
			db_name=target,
			service_name=service_name
		)
		if not bin:
			return frappe.throw(
				"{} not found in PATH! This is required to restore the database.".format(bin_name),
				exc=frappe.ExecutableNotFound,
			)
		command.append(bin)
		command.append(shlex.join(args))

		execute_in_shell(" ".join(command), check_exit_code=True, verbose=verbose)
		frappe.cache.delete_keys("")  # Delete all keys associated with this site.


class OracleDBExceptionUtil:
	ProgrammingError = oracledb.ProgrammingError
	TableMissingError = oracledb.ProgrammingError
	OperationalError = oracledb.OperationalError
	InternalError = oracledb.InternalError
	DataError = oracledb.DataError
	InterfaceError = oracledb.InterfaceError

	@staticmethod
	def is_deadlocked(e: oracledb.Error) -> bool:
		return 'ORA-00060' in str(e)  # deadlock detected

	@staticmethod
	def is_timedout(e: oracledb.Error) -> bool:
		return 'ORA-01013' in str(e)  # user requested cancel of current operation

	@staticmethod
	def is_read_only_mode_error(e: oracledb.Error) -> bool:
		return 'ORA-16000' in str(e)  # database open for read-only access

	@staticmethod
	def is_table_missing(e: oracledb.Error) -> bool:
		return 'ORA-00942' in str(e)  # table or view does not exist

	@staticmethod
	def is_missing_column(e: oracledb.Error) -> bool:
		return 'ORA-00904' in str(e)  # invalid identifier

	@staticmethod
	def is_duplicate_fieldname(e: oracledb.Error) -> bool:
		return 'ORA-00957' in str(e)  # duplicate column name

	@staticmethod
	def is_duplicate_entry(e: oracledb.Error) -> bool:
		return 'ORA-00001' in str(e)  # unique constraint violated

	@staticmethod
	def is_access_denied(e: oracledb.Error) -> bool:
		return 'ORA-01031' in str(e)  # insufficient privileges

	@staticmethod
	def cant_drop_field_or_key(e: oracledb.Error) -> bool:
		return 'ORA-02449' in str(e)  # cannot drop, column being used

	@staticmethod
	def is_syntax_error(e: oracledb.Error) -> bool:
		return 'ORA-00900' in str(e)  # invalid SQL statement

	@staticmethod
	def is_statement_timeout(e: oracledb.Error) -> bool:
		return 'ORA-01013' in str(e)  # user requested cancel of current operation

	@staticmethod
	def is_data_too_long(e: oracledb.Error) -> bool:
		return 'ORA-01401' in str(e)  # inserted value too large for column

	@staticmethod
	def is_db_table_size_limit(e: oracledb.Error) -> bool:
		return 'ORA-01438' in str(
			e)  # value larger than specified precision allowed for this column

	@staticmethod
	def is_primary_key_violation(e: oracledb.Error) -> bool:
		return OracleDBDatabase.is_duplicate_entry(e)

	@staticmethod
	def is_unique_key_violation(e: oracledb.Error) -> bool:
		return OracleDBDatabase.is_duplicate_entry(e)


class OracleDBConnectionUtil:
	def get_connection(self):
		if hasattr(self, "db_conn"):
			return self.db_conn

		if not hasattr(self, "db_dsn"):
			self.db_dsn = "{}:{}/{}".format(
				self.host, self.port, self.service_name
			)

		conn = oracledb.connect(
			dsn=self.db_dsn,
			user=self.user,
			password=self.password
		)
		self.db_conn = conn

		return self.db_conn

	def get_cursor(self):
		return self.get_connection().cursor()


class OracleDBDatabase(OracleDBExceptionUtil, OracleDBConnectionUtil, Database):
	REGEX_CHARACTER: str = "regexp"
	CONVERSION_MAP: dict = {
		oracledb.DB_TYPE_NUMBER: float,
		oracledb.DB_TYPE_TIMESTAMP: get_datetime,
		UnicodeWithAttrs: oracledb.makedsn,
	}
	default_port = "1521"  # Default OracleDB port

	def setup_type_map(self):
		self.db_type = "oracledb"
		self.type_map = {
			"Currency": ("NUMBER", "21,9"),
			"Int": ("NUMBER", "10"),
			"Long Int": ("NUMBER", "20"),
			"Float": ("NUMBER", "21,9"),
			"Percent": ("NUMBER", "21,9"),
			# todo: Could this be boolean?
			"Check": ("NUMBER", "3,0"),
			"Small Text": ("VARCHAR2", "4000"),
			"Long Text": ("VARCHAR2", "4000"),
			"Code": ("VARCHAR2", "4000"),
			"Text Editor": ("VARCHAR2", "4000"),
			"Markdown Editor": ("VARCHAR2", "4000"),
			"HTML Editor": ("VARCHAR2", "4000"),
			"Date": ("DATE", ""),
			"Datetime": ("TIMESTAMP", "6"),
			"Time": ("TIMESTAMP", "6"),
			"Text": ("VARCHAR2", "4000"),
			"Data": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Link": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Dynamic Link": ("VARCHAR2", self.VARCHAR_LEN, '4000'),
			"Password": ("VARCHAR2", "4000"),
			"Select": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Rating": ("NUMBER", "3,2"),
			"Read Only": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Attach": ("VARCHAR2", "4000"),
			"Attach Image": ("VARCHAR2", "4000"),
			"Signature": ("VARCHAR2", ""),
			"Color": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Barcode": ("VARCHAR2", "4000"),
			"Geolocation": ("VARCHAR2", "4000"),
			"Duration": ("NUMBER", "21,9"),
			"Icon": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Phone": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Autocomplete": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"JSON": ("VARCHAR2", "4000"),
		}

	def get_tables(self, cached=True):

		to_query = not cached

		if cached:
			tables = frappe.cache.get_value("db_tables")
			to_query = not tables

		if to_query:
			table_instance = frappe.qb.Table('all_tables')

			query = frappe.qb.from_(table_instance).select(table_instance.table_name).where(table_instance.tablespace_name.notin(["SYSTEM", "SYSAUX"]))

			tables = query.run(pluck=True)
			frappe.cache.set_value("db_tables", tables)

		return tables
