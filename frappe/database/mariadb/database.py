from typing import List, Tuple, Union

import pymysql
from pymysql.constants import ER, FIELD_TYPE
from pymysql.converters import conversions, escape_string

import frappe
from frappe.database.database import Database
from frappe.database.mariadb.schema import MariaDBTable
from frappe.utils import UnicodeWithAttrs, cstr, get_datetime, get_table_name


class MariaDBDatabase(Database):
	ProgrammingError = pymysql.err.ProgrammingError
	TableMissingError = pymysql.err.ProgrammingError
	OperationalError = pymysql.err.OperationalError
	InternalError = pymysql.err.InternalError
	SQLError = pymysql.err.ProgrammingError
	DataError = pymysql.err.DataError
	REGEX_CHARACTER = "regexp"

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
			"Rating": ("int", "1"),
			"Read Only": ("varchar", self.VARCHAR_LEN),
			"Attach": ("text", ""),
			"Attach Image": ("text", ""),
			"Signature": ("longtext", ""),
			"Color": ("varchar", self.VARCHAR_LEN),
			"Barcode": ("longtext", ""),
			"Geolocation": ("longtext", ""),
			"Duration": ("decimal", "21,9"),
			"Icon": ("varchar", self.VARCHAR_LEN),
		}

	def get_connection(self):
		usessl = 0
		if frappe.conf.db_ssl_ca and frappe.conf.db_ssl_cert and frappe.conf.db_ssl_key:
			usessl = 1
			ssl_params = {
				"ca": frappe.conf.db_ssl_ca,
				"cert": frappe.conf.db_ssl_cert,
				"key": frappe.conf.db_ssl_key,
			}

		conversions.update(
			{
				FIELD_TYPE.NEWDECIMAL: float,
				FIELD_TYPE.DATETIME: get_datetime,
				UnicodeWithAttrs: conversions[str],
			}
		)

		conn = pymysql.connect(
			user=self.user or "",
			password=self.password or "",
			host=self.host,
			port=self.port,
			charset="utf8mb4",
			use_unicode=True,
			ssl=ssl_params if usessl else None,
			conv=conversions,
			local_infile=frappe.conf.local_infile,
		)

		# MYSQL_OPTION_MULTI_STATEMENTS_OFF = 1
		# # self._conn.set_server_option(MYSQL_OPTION_MULTI_STATEMENTS_OFF)

		if self.user != "root":
			conn.select_db(self.user)

		return conn

	def set_execution_timeout(self, seconds: int):
		self.sql("set session max_statement_time = %s", int(seconds))

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

	@staticmethod
	def escape(s, percent=True):
		"""Excape quotes and percent in given string."""
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
		return code in (pymysql.DATE, pymysql.DATETIME)

	def rename_table(self, old_name: str, new_name: str) -> Union[List, Tuple]:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		return self.sql(f"RENAME TABLE `{old_name}` TO `{new_name}`")

	def describe(self, doctype: str) -> Union[List, Tuple]:
		table_name = get_table_name(doctype)
		return self.sql(f"DESC `{table_name}`")

	def change_column_type(self, table: str, column: str, type: str) -> Union[List, Tuple]:
		table_name = get_table_name(table)
		return self.sql(f"ALTER TABLE `{table_name}` MODIFY `{column}` {type} NOT NULL")

	# exception types
	@staticmethod
	def is_deadlocked(e):
		return e.args[0] == ER.LOCK_DEADLOCK

	@staticmethod
	def is_timedout(e):
		return e.args[0] == ER.LOCK_WAIT_TIMEOUT

	@staticmethod
	def is_statement_timeout(e):
		return e.args[0] == 1969

	@staticmethod
	def is_table_missing(e):
		return e.args[0] == ER.NO_SUCH_TABLE

	@staticmethod
	def is_missing_table(e):
		return MariaDBDatabase.is_table_missing(e)

	@staticmethod
	def is_missing_column(e):
		return e.args[0] == ER.BAD_FIELD_ERROR

	@staticmethod
	def is_duplicate_fieldname(e):
		return e.args[0] == ER.DUP_FIELDNAME

	@staticmethod
	def is_duplicate_entry(e):
		return e.args[0] == ER.DUP_ENTRY

	@staticmethod
	def is_access_denied(e):
		return e.args[0] == ER.ACCESS_DENIED_ERROR

	@staticmethod
	def cant_drop_field_or_key(e):
		return e.args[0] == ER.CANT_DROP_FIELD_OR_KEY

	@staticmethod
	def is_syntax_error(e):
		return e.args[0] == ER.PARSE_ERROR

	@staticmethod
	def is_data_too_long(e):
		return e.args[0] == ER.DATA_TOO_LONG

	def is_primary_key_violation(self, e):
		return self.is_duplicate_entry(e) and "PRIMARY" in cstr(e.args[1])

	def is_unique_key_violation(self, e):
		return self.is_duplicate_entry(e) and "Duplicate" in cstr(e.args[1])

	def create_auth_table(self):
		self.sql_ddl(
			"""create table if not exists `__Auth` (
				`doctype` VARCHAR(140) NOT NULL,
				`name` VARCHAR(255) NOT NULL,
				`fieldname` VARCHAR(140) NOT NULL,
				`password` TEXT NOT NULL,
				`encrypted` INT(1) NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
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

	def create_help_table(self):
		self.sql(
			"""create table help(
				path varchar(255),
				content text,
				title text,
				intro text,
				full_path text,
				fulltext(title),
				fulltext(content),
				index (path))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4"""
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

	def add_index(self, doctype, fields, index_name=None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		index_name = index_name or self.get_index_name(fields)
		table_name = "tab" + doctype
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
			raise Exception("Wrong doctype {0} in updatedb".format(doctype))

		if not res[0][0]:
			db_table = MariaDBTable(doctype, meta)
			db_table.validate()

			self.commit()
			db_table.sync()
			self.begin()

	def get_database_list(self, target):
		return [d[0] for d in self.sql("SHOW DATABASES;")]
