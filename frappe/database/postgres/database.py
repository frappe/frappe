import re

import psycopg2
import psycopg2.extensions
from psycopg2.errorcodes import (
	CLASS_INTEGRITY_CONSTRAINT_VIOLATION,
	DEADLOCK_DETECTED,
	DUPLICATE_COLUMN,
	INSUFFICIENT_PRIVILEGE,
	STRING_DATA_RIGHT_TRUNCATION,
	UNDEFINED_COLUMN,
	UNDEFINED_TABLE,
	UNIQUE_VIOLATION,
)
from psycopg2.errors import ReadOnlySqlTransaction, SequenceGeneratorLimitExceeded, SyntaxError
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ

import frappe
from frappe.database.database import Database
from frappe.database.postgres.schema import PostgresTable
from frappe.database.utils import EmptyQueryValues, LazyDecode
from frappe.utils import cstr, get_table_name

# cast decimals as floats
DEC2FLOAT = psycopg2.extensions.new_type(
	psycopg2.extensions.DECIMAL.values,
	"DEC2FLOAT",
	lambda value, curs: float(value) if value is not None else None,
)

psycopg2.extensions.register_type(DEC2FLOAT)

LOCATE_SUB_PATTERN = re.compile(r"locate\(([^,]+),([^)]+)(\)?)\)", flags=re.IGNORECASE)
LOCATE_QUERY_PATTERN = re.compile(r"locate\(", flags=re.IGNORECASE)
PG_TRANSFORM_PATTERN = re.compile(r"([=><]+)\s*([+-]?\d+)(\.0)?(?![a-zA-Z\.\d])")
FROM_TAB_PATTERN = re.compile(r"from tab([\w-]*)", flags=re.IGNORECASE)


class PostgresExceptionUtil:
	ProgrammingError = psycopg2.ProgrammingError
	TableMissingError = psycopg2.ProgrammingError
	OperationalError = psycopg2.OperationalError
	InternalError = psycopg2.InternalError
	SQLError = psycopg2.ProgrammingError
	DataError = psycopg2.DataError
	InterfaceError = psycopg2.InterfaceError
	SequenceGeneratorLimitExceeded = SequenceGeneratorLimitExceeded

	@staticmethod
	def is_deadlocked(e):
		return getattr(e, "pgcode", None) == DEADLOCK_DETECTED

	@staticmethod
	def is_timedout(e):
		# http://initd.org/psycopg/docs/extensions.html?highlight=datatype#psycopg2.extensions.QueryCanceledError
		return isinstance(e, psycopg2.extensions.QueryCanceledError)

	@staticmethod
	def is_read_only_mode_error(e) -> bool:
		return isinstance(e, ReadOnlySqlTransaction)

	@staticmethod
	def is_syntax_error(e):
		return isinstance(e, SyntaxError)

	@staticmethod
	def is_table_missing(e):
		return getattr(e, "pgcode", None) == UNDEFINED_TABLE

	@staticmethod
	def is_missing_table(e):
		return PostgresDatabase.is_table_missing(e)

	@staticmethod
	def is_missing_column(e):
		return getattr(e, "pgcode", None) == UNDEFINED_COLUMN

	@staticmethod
	def is_access_denied(e):
		return getattr(e, "pgcode", None) == INSUFFICIENT_PRIVILEGE

	@staticmethod
	def cant_drop_field_or_key(e):
		return getattr(e, "pgcode", None) == CLASS_INTEGRITY_CONSTRAINT_VIOLATION

	@staticmethod
	def is_duplicate_entry(e):
		return getattr(e, "pgcode", None) == UNIQUE_VIOLATION

	@staticmethod
	def is_primary_key_violation(e):
		return getattr(e, "pgcode", None) == UNIQUE_VIOLATION and "_pkey" in cstr(e.args[0])

	@staticmethod
	def is_unique_key_violation(e):
		return getattr(e, "pgcode", None) == UNIQUE_VIOLATION and "_key" in cstr(e.args[0])

	@staticmethod
	def is_duplicate_fieldname(e):
		return getattr(e, "pgcode", None) == DUPLICATE_COLUMN

	@staticmethod
	def is_statement_timeout(e):
		return PostgresDatabase.is_timedout(e) or isinstance(e, frappe.QueryTimeoutError)

	@staticmethod
	def is_data_too_long(e):
		return getattr(e, "pgcode", None) == STRING_DATA_RIGHT_TRUNCATION


class PostgresDatabase(PostgresExceptionUtil, Database):
	REGEX_CHARACTER = "~"
	default_port = "5432"

	def setup_type_map(self):
		self.db_type = "postgres"
		self.type_map = {
			"Currency": ("decimal", "21,9"),
			"Int": ("bigint", None),
			"Long Int": ("bigint", None),
			"Float": ("decimal", "21,9"),
			"Percent": ("decimal", "21,9"),
			"Check": ("smallint", None),
			"Small Text": ("text", ""),
			"Long Text": ("text", ""),
			"Code": ("text", ""),
			"Text Editor": ("text", ""),
			"Markdown Editor": ("text", ""),
			"HTML Editor": ("text", ""),
			"Date": ("date", ""),
			"Datetime": ("timestamp", None),
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
			"Signature": ("text", ""),
			"Color": ("varchar", self.VARCHAR_LEN),
			"Barcode": ("text", ""),
			"Geolocation": ("text", ""),
			"Duration": ("decimal", "21,9"),
			"Icon": ("varchar", self.VARCHAR_LEN),
			"Phone": ("varchar", self.VARCHAR_LEN),
			"Autocomplete": ("varchar", self.VARCHAR_LEN),
			"JSON": ("json", ""),
		}

	@property
	def last_query(self):
		return LazyDecode(self._cursor.query)

	def get_connection(self):
		conn = psycopg2.connect(
			"host='{}' dbname='{}' user='{}' password='{}' port={}".format(
				self.host, self.user, self.user, self.password, self.port
			)
		)
		conn.set_isolation_level(ISOLATION_LEVEL_REPEATABLE_READ)

		return conn

	def set_execution_timeout(self, seconds: int):
		# Postgres expects milliseconds as input
		self.sql("set local statement_timeout = %s", int(seconds) * 1000)

	def escape(self, s, percent=True):
		"""Escape quotes and percent in given string."""
		if isinstance(s, bytes):
			s = s.decode("utf-8")

		# MariaDB's driver treats None as an empty string
		# So Postgres should do the same

		if s is None:
			s = ""

		if percent:
			s = s.replace("%", "%%")

		s = s.encode("utf-8")

		return str(psycopg2.extensions.QuotedString(s))

	def get_database_size(self):
		"""'Returns database size in MB"""
		db_size = self.sql(
			"SELECT (pg_database_size(%s) / 1024 / 1024) as database_size", self.db_name, as_dict=True
		)
		return db_size[0].get("database_size")

	# pylint: disable=W0221
	def sql(self, query, values=EmptyQueryValues, *args, **kwargs):
		return super().sql(modify_query(query), modify_values(values), *args, **kwargs)

	def lazy_mogrify(self, *args, **kwargs) -> str:
		return self.last_query

	def get_tables(self, cached=True):
		return [
			d[0]
			for d in self.sql(
				"""select table_name
			from information_schema.tables
			where table_catalog='{}'
				and table_type = 'BASE TABLE'
				and table_schema='{}'""".format(
					frappe.conf.db_name, frappe.conf.get("db_schema", "public")
				)
			)
		]

	def format_date(self, date):
		if not date:
			return "0001-01-01"

		if not isinstance(date, str):
			date = date.strftime("%Y-%m-%d")

		return date

	# column type
	@staticmethod
	def is_type_number(code):
		return code == psycopg2.NUMBER

	@staticmethod
	def is_type_datetime(code):
		return code == psycopg2.DATETIME

	def rename_table(self, old_name: str, new_name: str) -> list | tuple:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		return self.sql(f"ALTER TABLE `{old_name}` RENAME TO `{new_name}`")

	def describe(self, doctype: str) -> list | tuple:
		table_name = get_table_name(doctype)
		return self.sql(
			f"SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_NAME = '{table_name}'"
		)

	def change_column_type(
		self, doctype: str, column: str, type: str, nullable: bool = False, use_cast: bool = False
	) -> list | tuple:
		table_name = get_table_name(doctype)
		null_constraint = "SET NOT NULL" if not nullable else "DROP NOT NULL"
		using_cast = f'using "{column}"::{type}' if use_cast else ""

		# postgres allows ddl in transactions but since we've currently made
		# things same as mariadb (raising exception on ddl commands if the transaction has any writes),
		# hence using sql_ddl here for committing and then moving forward.
		return self.sql_ddl(
			f"""ALTER TABLE "{table_name}"
				ALTER COLUMN "{column}" TYPE {type} {using_cast},
				ALTER COLUMN "{column}" {null_constraint}"""
		)

	def create_auth_table(self):
		self.sql_ddl(
			"""create table if not exists "__Auth" (
				"doctype" VARCHAR(140) NOT NULL,
				"name" VARCHAR(255) NOT NULL,
				"fieldname" VARCHAR(140) NOT NULL,
				"password" TEXT NOT NULL,
				"encrypted" INT NOT NULL DEFAULT 0,
				PRIMARY KEY ("doctype", "name", "fieldname")
			)"""
		)

	def create_global_search_table(self):
		if not "__global_search" in self.get_tables():
			self.sql(
				"""create table "__global_search"(
				doctype varchar(100),
				name varchar({0}),
				title varchar({0}),
				content text,
				route varchar({0}),
				published int not null default 0,
				unique (doctype, name))""".format(
					self.VARCHAR_LEN
				)
			)

	def create_user_settings_table(self):
		self.sql_ddl(
			"""create table if not exists "__UserSettings" (
			"user" VARCHAR(180) NOT NULL,
			"doctype" VARCHAR(180) NOT NULL,
			"data" TEXT,
			UNIQUE ("user", "doctype")
			)"""
		)

	def updatedb(self, doctype, meta=None):
		"""
		Syncs a `DocType` to the table
		* creates if required
		* updates columns
		* updates indices
		"""
		res = self.sql(f"select issingle from `tabDocType` where name='{doctype}'")
		if not res:
			raise Exception(f"Wrong doctype {doctype} in updatedb")

		if not res[0][0]:
			db_table = PostgresTable(doctype, meta)
			db_table.validate()

			self.commit()
			db_table.sync()
			self.begin()

	@staticmethod
	def get_on_duplicate_update(key="name"):
		if isinstance(key, list):
			key = '", "'.join(key)
		return f'ON CONFLICT ("{key}") DO UPDATE SET '

	def check_implicit_commit(self, query):
		pass  # postgres can run DDL in transactions without implicit commits

	def has_index(self, table_name, index_name):
		return self.sql(
			"""SELECT 1 FROM pg_indexes WHERE tablename='{table_name}'
			and indexname='{index_name}' limit 1""".format(
				table_name=table_name, index_name=index_name
			)
		)

	def add_index(self, doctype: str, fields: list, index_name: str = None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		table_name = get_table_name(doctype)
		index_name = index_name or self.get_index_name(fields)
		fields_str = '", "'.join(re.sub(r"\(.*\)", "", field) for field in fields)

		self.sql_ddl(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{table_name}` ("{fields_str}")')

	def add_unique(self, doctype, fields, constraint_name=None):
		if isinstance(fields, str):
			fields = [fields]
		if not constraint_name:
			constraint_name = "unique_" + "_".join(fields)

		if not self.sql(
			"""
			SELECT CONSTRAINT_NAME
			FROM information_schema.TABLE_CONSTRAINTS
			WHERE table_name=%s
			AND constraint_type='UNIQUE'
			AND CONSTRAINT_NAME=%s""",
			("tab" + doctype, constraint_name),
		):
			self.commit()
			self.sql(
				"""ALTER TABLE `tab%s`
					ADD CONSTRAINT %s UNIQUE (%s)"""
				% (doctype, constraint_name, ", ".join(fields))
			)

	def get_table_columns_description(self, table_name):
		"""Returns list of column and its description"""
		# pylint: disable=W1401
		return self.sql(
			"""
			SELECT a.column_name AS name,
			CASE LOWER(a.data_type)
				WHEN 'character varying' THEN CONCAT('varchar(', a.character_maximum_length ,')')
				WHEN 'timestamp without time zone' THEN 'timestamp'
				ELSE a.data_type
			END AS type,
			BOOL_OR(b.index) AS index,
			SPLIT_PART(COALESCE(a.column_default, NULL), '::', 1) AS default,
			BOOL_OR(b.unique) AS unique
			FROM information_schema.columns a
			LEFT JOIN
				(SELECT indexdef, tablename,
					indexdef LIKE '%UNIQUE INDEX%' AS unique,
					indexdef NOT LIKE '%UNIQUE INDEX%' AS index
					FROM pg_indexes
					WHERE tablename='{table_name}') b
				ON SUBSTRING(b.indexdef, '(.*)') LIKE CONCAT('%', a.column_name, '%')
			WHERE a.table_name = '{table_name}'
			GROUP BY a.column_name, a.data_type, a.column_default, a.character_maximum_length;
		""".format(
				table_name=table_name
			),
			as_dict=1,
		)

	def get_database_list(self):
		return self.sql("SELECT datname FROM pg_database", pluck=True)


def modify_query(query):
	""" "Modifies query according to the requirements of postgres"""
	# replace ` with " for definitions
	query = str(query).replace("`", '"')
	query = replace_locate_with_strpos(query)
	# select from requires ""
	query = FROM_TAB_PATTERN.sub(r'from "tab\1"', query)

	# only find int (with/without signs), ignore decimals (with/without signs), ignore hashes (which start with numbers),
	# drop .0 from decimals and add quotes around them
	#
	# >>> query = "c='abcd' , a >= 45, b = -45.0, c =   40, d=4500.0, e=3500.53, f=40psdfsd, g=9092094312, h=12.00023"
	# >>> re.sub(r"([=><]+)\s*([+-]?\d+)(\.0)?(?![a-zA-Z\.\d])", r"\1 '\2'", query)
	# 	"c='abcd' , a >= '45', b = '-45', c = '40', d= '4500', e=3500.53, f=40psdfsd, g= '9092094312', h=12.00023

	return PG_TRANSFORM_PATTERN.sub(r"\1 '\2'", query)


def modify_values(values):
	def modify_value(value):
		if isinstance(value, (list, tuple)):
			value = tuple(modify_values(value))

		elif isinstance(value, int):
			value = str(value)

		return value

	if not values or values == EmptyQueryValues:
		return values

	if isinstance(values, dict):
		for k, v in values.items():
			values[k] = modify_value(v)
	elif isinstance(values, (tuple, list)):
		new_values = []
		for val in values:
			new_values.append(modify_value(val))

		values = new_values
	else:
		values = modify_value(values)

	return values


def replace_locate_with_strpos(query):
	# strpos is the locate equivalent in postgres
	if LOCATE_QUERY_PATTERN.search(query):
		query = LOCATE_SUB_PATTERN.sub(r"strpos(\2\3, \1)", query)
	return query
