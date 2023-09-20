import re

import pymysql
from pymysql.constants import ER, FIELD_TYPE
from pymysql.converters import conversions, escape_string

import frappe
from frappe.database.database import Database
from frappe.database.mariadb.schema import MariaDBTable
from frappe.utils import UnicodeWithAttrs, cstr, get_datetime, get_table_name

_PARAM_COMP = re.compile(r"%\([\w]*\)s")


class MariaDBExceptionUtil:
	ProgrammingError = pymysql.ProgrammingError
	TableMissingError = pymysql.ProgrammingError
	OperationalError = pymysql.OperationalError
	InternalError = pymysql.InternalError
	SQLError = pymysql.ProgrammingError
	DataError = pymysql.DataError

	# match ER_SEQUENCE_RUN_OUT - https://mariadb.com/kb/en/mariadb-error-codes/
	SequenceGeneratorLimitExceeded = pymysql.OperationalError
	SequenceGeneratorLimitExceeded.errno = 4084

	@staticmethod
	def is_deadlocked(e: pymysql.Error) -> bool:
		return e.args[0] == ER.LOCK_DEADLOCK

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
			"host": self.host,
			"user": self.user,
			"password": self.password,
			"conv": self.CONVERSION_MAP,
			"charset": "utf8mb4",
			"use_unicode": True,
		}

		if self.user not in (frappe.flags.root_login, "root"):
			conn_settings["database"] = self.user

		if self.port:
			conn_settings["port"] = int(self.port)

		if frappe.conf.local_infile:
			conn_settings["local_infile"] = frappe.conf.local_infile

		if frappe.conf.db_ssl_ca and frappe.conf.db_ssl_cert and frappe.conf.db_ssl_key:
			conn_settings["ssl"] = {
				"ca": frappe.conf.db_ssl_ca,
				"cert": frappe.conf.db_ssl_cert,
				"key": frappe.conf.db_ssl_key,
			}
		return conn_settings


class MariaDBDatabase(MariaDBConnectionUtil, MariaDBExceptionUtil, Database):
	REGEX_CHARACTER = "regexp"
	CONVERSION_MAP = conversions | {
		FIELD_TYPE.NEWDECIMAL: float,
		FIELD_TYPE.DATETIME: get_datetime,
		UnicodeWithAttrs: escape_string,
	}
	default_port = "3306"

	def setup_type_map(self):
		self.db_type = "mariadb"
		self.type_map = {
			"Currency": ("decimal", "21,9"),
			"Int": ("int", "11"),
			"Long Int": ("bigint", "20"),
			"Float": ("decimal", "21,9"),
			"Percent": ("decimal", "21,9"),
			"Check": ("int", "1"),
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
		"""'Returns database size in MB"""
		db_size = self.sql(
			"""
			SELECT `table_schema` as `database_name`,
			SUM(`data_length` + `index_length`) / 1024 / 1024 AS `database_size`
			FROM information_schema.tables WHERE `table_schema` = %s GROUP BY `table_schema`
			""",
			self.db_name,
			as_dict=True,
		)

		return db_size[0].get("database_size")

	def log_query(self, query, values, debug, explain):
		self.last_query = self._cursor._executed
		self._log_query(self.last_query, debug, explain, query)
		return self.last_query

	@staticmethod
	def escape(s, percent=True):
		"""Excape quotes and percent in given string."""
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

	def create_auth_table(self):
		self.sql_ddl(
			"""create table if not exists `__Auth` (
				`doctype` VARCHAR(140) NOT NULL,
				`name` VARCHAR(255) NOT NULL,
				`fieldname` VARCHAR(140) NOT NULL,
				`password` TEXT NOT NULL,
				`encrypted` INT(1) NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
		)

	def create_global_search_table(self):
		if not "__global_search" in self.get_tables():
			self.sql(
				"""create table __global_search(
				doctype varchar(100),
				name varchar({0}),
				title varchar({0}),
				content text,
				fulltext(content),
				route varchar({0}),
				published int(1) not null default 0,
				unique `doctype_name` (doctype, name))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4""".format(
					self.VARCHAR_LEN
				)
			)

	def create_user_settings_table(self):
		self.sql_ddl(
			"""create table if not exists __UserSettings (
			`user` VARCHAR(180) NOT NULL,
			`doctype` VARCHAR(180) NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8"""
		)

	@staticmethod
	def get_on_duplicate_update(key=None):
		return "ON DUPLICATE key UPDATE "

	def get_table_columns_description(self, table_name):
		"""Returns list of column and its description"""
		return self.sql(
			"""select
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
			column_key = 'UNI' as 'unique'
			from information_schema.columns as columns
			where table_name = '{table_name}' """.format(
				table_name=table_name
			),
			as_dict=1,
		)

	def has_index(self, table_name, index_name):
		return self.sql(
			"""SHOW INDEX FROM `{table_name}`
			WHERE Key_name='{index_name}'""".format(
				table_name=table_name, index_name=index_name
			)
		)

	def get_column_index(
		self, table_name: str, fieldname: str, unique: bool = False
	) -> frappe._dict | None:
		"""Check if column exists for a specific fields in specified order.

		This differs from db.has_index because it doesn't rely on index name but columns inside an
		index.
		"""

		indexes = self.sql(
			f"""SHOW INDEX FROM `{table_name}`
				WHERE Column_name = "{fieldname}"
					AND Seq_in_index = 1
					AND Non_unique={int(not unique)}
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

	def add_index(self, doctype: str, fields: list, index_name: str = None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		index_name = index_name or self.get_index_name(fields)
		table_name = get_table_name(doctype)
		if not self.has_index(table_name, index_name):
			self.commit()
			self.sql(
				"""ALTER TABLE `%s`
				ADD INDEX `%s`(%s)"""
				% (table_name, index_name, ", ".join(fields))
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
				"""alter table `tab%s`
					add unique `%s`(%s)"""
				% (doctype, constraint_name, ", ".join(fields))
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

			self.commit()
			db_table.sync()
			self.begin()

	def get_database_list(self):
		return self.sql("SHOW DATABASES", pluck=True)

	def get_tables(self, cached=True):
		"""Returns list of tables"""
		to_query = not cached

		if cached:
			tables = frappe.cache().get_value("db_tables")
			to_query = not tables

		if to_query:
			information_schema = frappe.qb.Schema("information_schema")

			tables = (
				frappe.qb.from_(information_schema.tables)
				.select(information_schema.tables.table_name)
				.where(information_schema.tables.table_schema != "information_schema")
				.run(pluck=True)
			)
			frappe.cache().set_value("db_tables", tables)

		return tables
