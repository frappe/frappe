from contextlib import contextmanager

import pymysql
from pymysql.constants import ER, FIELD_TYPE
from pymysql.converters import conversions, escape_string

import frappe
from frappe.database.database import Database
from frappe.database.mariadb.schema import MariaDBTable
from frappe.utils import UnicodeWithAttrs, cstr, get_datetime, get_table_name


class MariaDBExceptionUtil:
	ProgrammingError = pymysql.ProgrammingError
	TableMissingError = pymysql.ProgrammingError
	OperationalError = pymysql.OperationalError
	InternalError = pymysql.InternalError
	SQLError = pymysql.ProgrammingError
	DataError = pymysql.DataError
	InterfaceError = pymysql.InterfaceError

	# match ER_SEQUENCE_RUN_OUT - https://mariadb.com/kb/en/mariadb-error-codes/
	SequenceGeneratorLimitExceeded = pymysql.OperationalError
	SequenceGeneratorLimitExceeded.errno = 4084

	@staticmethod
	def is_deadlocked(e: pymysql.Error) -> bool:
		# Snapshot isolation is also treated as deadlock from User POV
		return e.args[0] in (ER.LOCK_DEADLOCK, ER.CHECKREAD)

	@staticmethod
	def is_timedout(e: pymysql.Error) -> bool:
		return e.args[0] == ER.LOCK_WAIT_TIMEOUT

	@staticmethod
	def is_read_only_mode_error(e: pymysql.Error) -> bool:
		return e.args[0] == 1792

	@staticmethod
	def is_table_missing(e: pymysql.Error) -> bool:
		return e.args[0] == ER.NO_SUCH_TABLE

	@staticmethod
	def is_missing_table(e: pymysql.Error) -> bool:
		return MariaDBDatabase.is_table_missing(e)

	@staticmethod
	def is_missing_column(e: pymysql.Error) -> bool:
		return e.args[0] == ER.BAD_FIELD_ERROR

	@staticmethod
	def is_duplicate_fieldname(e: pymysql.Error) -> bool:
		return e.args[0] == ER.DUP_FIELDNAME

	@staticmethod
	def is_duplicate_entry(e: pymysql.Error) -> bool:
		return e.args[0] == ER.DUP_ENTRY

	@staticmethod
	def is_access_denied(e: pymysql.Error) -> bool:
		return e.args[0] == ER.ACCESS_DENIED_ERROR

	@staticmethod
	def cant_drop_field_or_key(e: pymysql.Error) -> bool:
		return e.args[0] == ER.CANT_DROP_FIELD_OR_KEY

	@staticmethod
	def is_syntax_error(e: pymysql.Error) -> bool:
		return e.args[0] == ER.PARSE_ERROR

	@staticmethod
	def is_statement_timeout(e: pymysql.Error) -> bool:
		return e.args[0] == 1969

	@staticmethod
	def is_data_too_long(e: pymysql.Error) -> bool:
		return e.args[0] == ER.DATA_TOO_LONG

	@staticmethod
	def is_db_table_size_limit(e: pymysql.Error) -> bool:
		return e.args[0] == ER.TOO_BIG_ROWSIZE

	@staticmethod
	def is_primary_key_violation(e: pymysql.Error) -> bool:
		return (
			MariaDBDatabase.is_duplicate_entry(e)
			and "PRIMARY" in cstr(e.args[1])
			and isinstance(e, pymysql.IntegrityError)
		)

	@staticmethod
	def is_unique_key_violation(e: pymysql.Error) -> bool:
		return (
			MariaDBDatabase.is_duplicate_entry(e)
			and "Duplicate" in cstr(e.args[1])
			and isinstance(e, pymysql.IntegrityError)
		)

	@staticmethod
	def is_interface_error(e: pymysql.Error):
		return isinstance(e, pymysql.InterfaceError)


class MariaDBConnectionUtil:
	def get_connection(self):
		conn = self._get_connection()
		conn.auto_reconnect = True
		return conn

	def _get_connection(self):
		"""Return MariaDB connection object."""
		return self.create_connection()

	def create_connection(self):
		return pymysql.connect(**self.get_connection_settings())

	def set_execution_timeout(self, seconds: int):
		self.sql("set session max_statement_time = %s", int(seconds))

	def get_connection_settings(self) -> dict:
		conn_settings = {
			"user": self.user,
			"conv": self.CONVERSION_MAP,
			"charset": "utf8mb4",
			"collation": "utf8mb4_unicode_ci",
			"use_unicode": True,
		}

		if self.cur_db_name:
			conn_settings["database"] = self.cur_db_name

		if self.socket:
			conn_settings["unix_socket"] = self.socket
		else:
			conn_settings["host"] = self.host
			if self.port:
				conn_settings["port"] = int(self.port)

		if self.password:
			conn_settings["password"] = self.password

		if frappe.conf.local_infile:
			conn_settings["local_infile"] = frappe.conf.local_infile

		# Configure SSL settings
		if frappe.conf.db_ssl_ca:
			ssl_config = {
				"ca": frappe.conf.db_ssl_ca,
				"check_hostname": frappe.conf.db_ssl_check_hostname,
			}

			# Add client certificates for mutual SSL if available
			if frappe.conf.db_ssl_cert and frappe.conf.db_ssl_key:
				ssl_config.update({"cert": frappe.conf.db_ssl_cert, "key": frappe.conf.db_ssl_key})

			conn_settings["ssl"] = ssl_config

		return conn_settings


class MariaDBDatabase(MariaDBConnectionUtil, MariaDBExceptionUtil, Database):
	REGEX_CHARACTER = "regexp"
	CONVERSION_MAP = conversions | {
		FIELD_TYPE.NEWDECIMAL: float,
		FIELD_TYPE.DATETIME: get_datetime,
		UnicodeWithAttrs: escape_string,
	}
	default_port = "3306"
	MAX_ROW_SIZE_LIMIT = 65_535  # bytes

	def setup_type_map(self):
		self.db_type = "mariadb"
		self.type_map = {
			"Currency": ("decimal", "21,9"),
			"Int": ("int", "11"),
			"Long Int": ("bigint", "20"),
			"Float": ("decimal", "21,9"),
			"Percent": ("decimal", "21,9"),
			"Check": ("tinyint", 4),
			"Small Text": ("text", ""),
			"Long Text": ("longtext", ""),
			"Code": ("longtext", ""),
			"Text Editor": ("longtext", ""),
			"Markdown Editor": ("longtext", ""),
			"HTML Editor": ("longtext", ""),
			"Date": ("date", ""),
			"Datetime": ("datetime", "6"),
			"Time": ("time", "6"),
			"Text": ("text", ""),
			"Data": ("varchar", self.VARCHAR_LEN),
			"Link": ("varchar", self.VARCHAR_LEN),
			"Dynamic Link": ("varchar", self.VARCHAR_LEN),
			"Password": ("text", ""),
			"Select": ("varchar", self.VARCHAR_LEN),
			"Rating": ("decimal", "3,2"),
			"Read Only": ("varchar", self.VARCHAR_LEN),
			"Attach": ("text", ""),
			"Attach Image": ("text", ""),
			"Signature": ("longtext", ""),
			"Color": ("varchar", self.VARCHAR_LEN),
			"Barcode": ("longtext", ""),
			"Geolocation": ("longtext", ""),
			"Duration": ("decimal", "21,9"),
			"Icon": ("varchar", self.VARCHAR_LEN),
			"Phone": ("varchar", self.VARCHAR_LEN),
			"Autocomplete": ("varchar", self.VARCHAR_LEN),
			"JSON": ("json", ""),
		}

	def get_database_size(self):
		"""Return database size in MB."""
		db_size = self.sql(
			"""
			SELECT `table_schema` as `database_name`,
			SUM(`data_length` + `index_length`) / 1024 / 1024 AS `database_size`
			FROM information_schema.tables WHERE `table_schema` = %s GROUP BY `table_schema`
			""",
			self.cur_db_name,
			as_dict=True,
		)

		return db_size[0].get("database_size")

	def log_query(self, query, query_type, values, debug):
		mogrified_query = self._cursor._executed
		self.last_query = mogrified_query
		self._log_query(mogrified_query, query_type, debug, query)
		return mogrified_query

	def _clean_up(self):
		# PERF: Erase internal references of pymysql to trigger GC as soon as
		# results are consumed.
		self._cursor._result = None
		self._cursor._rows = None
		self._cursor.connection._result = None

	@staticmethod
	def escape(s, percent=True):
		"""Escape quotes and percent in given string."""
		# Update: We've scrapped PyMySQL in favour of MariaDB's official Python client
		# Also, given we're promoting use of the PyPika builder via frappe.qb, the use
		# of this method should be limited.

		# pymysql expects unicode argument to escape_string with Python 3
		s = frappe.as_unicode(escape_string(frappe.as_unicode(s)), "utf-8").replace("`", "\\`")

		# NOTE separating % escape, because % escape should only be done when using LIKE operator
		# or when you use python format string to generate query that already has a %s
		# for example: sql("select name from `tabUser` where name=%s and {0}".format(conditions), something)
		# defaulting it to True, as this is the most frequent use case
		# ideally we shouldn't have to use ESCAPE and strive to pass values via the values argument of sql
		if percent:
			s = s.replace("%", "%%")

		return "'" + s + "'"

	# column type
	@staticmethod
	def is_type_number(code):
		return code == pymysql.NUMBER

	@staticmethod
	def is_type_datetime(code):
		return code == pymysql.DATETIME

	def rename_table(self, old_name: str, new_name: str) -> list | tuple:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		return self.sql(f"RENAME TABLE `{old_name}` TO `{new_name}`")

	def describe(self, doctype: str) -> list | tuple:
		table_name = get_table_name(doctype)
		return self.sql(f"DESC `{table_name}`")

	def change_column_type(
		self, doctype: str, column: str, type: str, nullable: bool = False
	) -> list | tuple:
		table_name = get_table_name(doctype)
		null_constraint = "NOT NULL" if not nullable else ""
		return self.sql_ddl(f"ALTER TABLE `{table_name}` MODIFY `{column}` {type} {null_constraint}")

	def rename_column(self, doctype: str, old_column_name, new_column_name):
		current_data_type = self.get_column_type(doctype, old_column_name)

		table_name = get_table_name(doctype)

		frappe.db.sql_ddl(
			f"""ALTER TABLE `{table_name}`
				CHANGE COLUMN `{old_column_name}`
				`{new_column_name}`
				{current_data_type}"""
			# ^ Mariadb requires passing current data type again even if there's no change
			# This requirement is gone from v10.5
		)

	def create_auth_table(self):
		self.sql_ddl(
			"""create table if not exists `__Auth` (
				`doctype` VARCHAR(140) NOT NULL,
				`name` VARCHAR(255) NOT NULL,
				`fieldname` VARCHAR(140) NOT NULL,
				`password` TEXT NOT NULL,
				`encrypted` TINYINT NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
		)

	def create_global_search_table(self):
		if "__global_search" not in self.get_tables():
			self.sql(
				f"""create table __global_search(
				doctype varchar(100),
				name varchar({self.VARCHAR_LEN}),
				title varchar({self.VARCHAR_LEN}),
				content text,
				fulltext(content),
				route varchar({self.VARCHAR_LEN}),
				published TINYINT not null default 0,
				unique `doctype_name` (doctype, name))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4"""
			)

	def create_user_settings_table(self):
		self.sql_ddl(
			"""create table if not exists __UserSettings (
			`user` VARCHAR(180) NOT NULL,
			`doctype` VARCHAR(180) NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
		)

	@staticmethod
	def get_on_duplicate_update():
		return "ON DUPLICATE key UPDATE "

	def get_table_columns_description(self, table_name):
		"""Return list of columns with descriptions."""
		return self.sql(
			f"""select
			column_name as 'name',
			column_type as 'type',
			column_default as 'default',
			COALESCE(
				(select 1
				from information_schema.statistics
				where table_name="{table_name}"
					and column_name=columns.column_name
					and NON_UNIQUE=1
					and Seq_in_index = 1
					limit 1
			), 0) as 'index',
			column_key = 'UNI' as 'unique',
			(is_nullable = 'NO') AS 'not_nullable'
			from information_schema.columns as columns
			where table_name = '{table_name}'
   			and table_schema = '{frappe.db.cur_db_name}' """,
			as_dict=1,
		)

	def get_column_type(self, doctype, column):
		"""Return column type from database."""
		information_schema = frappe.qb.Schema("information_schema")
		table = get_table_name(doctype)

		return (
			frappe.qb.from_(information_schema.columns)
			.select(information_schema.columns.column_type)
			.where(
				(information_schema.columns.table_name == table)
				& (information_schema.columns.column_name == column)
				& (information_schema.columns.table_schema == self.cur_db_name)
			)
			.run(pluck=True)[0]
		)

	def has_index(self, table_name, index_name):
		return self.sql(
			f"""SHOW INDEX FROM `{table_name}`
			WHERE Key_name='{index_name}'"""
		)

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False) -> frappe._dict | None:
		"""Check if column exists for a specific fields in specified order.

		This differs from db.has_index because it doesn't rely on index name but columns inside an
		index.
		"""

		indexes = self.sql(
			f"""SHOW INDEX FROM `{table_name}`
				WHERE Column_name = "{fieldname}"
					AND Seq_in_index = 1
					AND Non_unique={int(not unique)}
					AND Index_type != 'FULLTEXT'
				""",
			as_dict=True,
		)

		# Same index can be part of clustered index which contains more fields
		# We don't want those.
		for index in indexes:
			clustered_index = self.sql(
				f"""SHOW INDEX FROM `{table_name}`
					WHERE Key_name = "{index.Key_name}"
						AND Seq_in_index = 2
					""",
				as_dict=True,
			)
			if not clustered_index:
				return index

	def add_index(self, doctype: str, fields: list, index_name: str | None = None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		index_name = index_name or self.get_index_name(fields)
		table_name = get_table_name(doctype)
		if not self.has_index(table_name, index_name):
			self.commit()
			self.sql(
				"""ALTER TABLE `{}`
				ADD INDEX IF NOT EXISTS `{}`({})""".format(table_name, index_name, ", ".join(fields))
			)
			# Ensure that DB migration doesn't clear this index, assuming this is manually added
			# via code or console.
			if len(fields) == 1 and not (frappe.flags.in_install or frappe.flags.in_migrate):
				make_property_setter(
					doctype,
					fields[0],
					property="search_index",
					value="1",
					property_type="Check",
					for_doctype=False,  # Applied on docfield
				)

	def add_unique(self, doctype, fields, constraint_name=None):
		if isinstance(fields, str):
			fields = [fields]
		if not constraint_name:
			constraint_name = "unique_" + "_".join(fields)

		if not self.sql(
			"""select CONSTRAINT_NAME from information_schema.TABLE_CONSTRAINTS
			where table_name=%s and constraint_type='UNIQUE' and CONSTRAINT_NAME=%s""",
			("tab" + doctype, constraint_name),
		):
			self.commit()
			self.sql(
				"""alter table `tab{}`
					add unique `{}`({})""".format(doctype, constraint_name, ", ".join(fields))
			)

	def updatedb(self, doctype, meta=None):
		"""
		Syncs a `DocType` to the table
		* creates if required
		* updates columns
		* updates indices
		"""
		res = self.sql("select issingle from `tabDocType` where name=%s", (doctype,))
		if not res:
			raise Exception(f"Wrong doctype {doctype} in updatedb")

		if not res[0][0]:
			db_table = MariaDBTable(doctype, meta)
			db_table.validate()

			db_table.sync()
			self.commit()

	def get_database_list(self):
		return self.sql("SHOW DATABASES", pluck=True)

	def get_tables(self, cached=True):
		"""Return list of tables."""
		to_query = not cached

		if cached:
			tables = frappe.client_cache.get_value("db_tables")
			to_query = not tables

		if to_query:
			information_schema = frappe.qb.Schema("information_schema")

			tables = (
				frappe.qb.from_(information_schema.tables)
				.select(information_schema.tables.table_name)
				.where(information_schema.tables.table_schema == frappe.db.cur_db_name)
				.run(pluck=True)
			)
			frappe.client_cache.set_value("db_tables", tables)

		return tables

	def get_row_size(self, doctype: str) -> int:
		"""Get estimated max row size of any table in bytes."""

		# Query reused from this answer: https://dba.stackexchange.com/a/313889/274503
		# Modification: get values for particular table instead of full summary.
		# Reference: https://mariadb.com/kb/en/data-type-storage-requirements/

		est_row_size = frappe.db.sql(
			"""
			SELECT SUM(col_sizes.col_size) AS EST_MAX_ROW_SIZE
			FROM (
				SELECT
					cols.COLUMN_NAME,
					CASE cols.DATA_TYPE
						WHEN 'tinyint' THEN 1
						WHEN 'smallint' THEN 2
						WHEN 'mediumint' THEN 3
						WHEN 'int' THEN 4
						WHEN 'bigint' THEN 8
						WHEN 'float' THEN IF(cols.NUMERIC_PRECISION > 24, 8, 4)
						WHEN 'double' THEN 8
						WHEN 'decimal' THEN ((cols.NUMERIC_PRECISION - cols.NUMERIC_SCALE) DIV 9)*4  + (cols.NUMERIC_SCALE DIV 9)*4 + CEIL(MOD(cols.NUMERIC_PRECISION - cols.NUMERIC_SCALE,9)/2) + CEIL(MOD(cols.NUMERIC_SCALE,9)/2)
						WHEN 'bit' THEN (cols.NUMERIC_PRECISION + 7) DIV 8
						WHEN 'year' THEN 1
						WHEN 'date' THEN 3
						WHEN 'time' THEN 3 + CEIL(cols.DATETIME_PRECISION /2)
						WHEN 'datetime' THEN 5 + CEIL(cols.DATETIME_PRECISION /2)
						WHEN 'timestamp' THEN 4 + CEIL(cols.DATETIME_PRECISION /2)
						WHEN 'char' THEN cols.CHARACTER_OCTET_LENGTH
						WHEN 'binary' THEN cols.CHARACTER_OCTET_LENGTH
						WHEN 'varchar' THEN IF(cols.CHARACTER_OCTET_LENGTH > 255, 2, 1) + cols.CHARACTER_OCTET_LENGTH
						WHEN 'varbinary' THEN IF(cols.CHARACTER_OCTET_LENGTH > 255, 2, 1) + cols.CHARACTER_OCTET_LENGTH
						WHEN 'tinyblob' THEN 9
						WHEN 'tinytext' THEN 9
						WHEN 'blob' THEN 10
						WHEN 'text' THEN 10
						WHEN 'mediumblob' THEN 11
						WHEN 'mediumtext' THEN 11
						WHEN 'longblob' THEN 12
						WHEN 'longtext' THEN 12
						WHEN 'enum' THEN 2
						WHEN 'set' THEN 8
						ELSE 0
					END AS col_size
				FROM INFORMATION_SCHEMA.COLUMNS cols
				WHERE cols.TABLE_NAME = %s
			) AS col_sizes;""",
			(get_table_name(doctype),),
		)

		if est_row_size:
			return int(est_row_size[0][0])

	@contextmanager
	def unbuffered_cursor(self):
		from pymysql.cursors import SSCursor

		try:
			if not self._conn:
				self.connect()

			original_cursor = self._cursor
			new_cursor = self._cursor = self._conn.cursor(SSCursor)
			yield
		finally:
			self._cursor = original_cursor
			new_cursor.close()

	def estimate_count(self, doctype: str):
		"""Get estimated count of total rows in a table."""
		from frappe.utils.data import cint

		table = get_table_name(doctype)

		count = self.sql("select table_rows from information_schema.tables where table_name = %s", table)
		return cint(count[0][0]) if count else 0
