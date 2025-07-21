import re
import sqlite3
import warnings
from datetime import date, datetime, time
from pathlib import Path

import frappe
from frappe.database.database import (
	TRANSACTION_DISABLED_MSG,
	Database,
	ImplicitCommitError,
)
from frappe.database.sqlite.schema import SQLiteTable
from frappe.utils import get_table_name

_PARAM_COMP = re.compile(r"%\([\w]*\)s")
IMPLICIT_COMMIT_QUERY_TYPES = frozenset(("start", "alter", "drop", "create", "truncate"))


class SQLiteExceptionUtil:
	ProgrammingError = sqlite3.ProgrammingError
	TableMissingError = sqlite3.OperationalError
	OperationalError = sqlite3.OperationalError
	InternalError = sqlite3.InternalError
	SQLError = sqlite3.OperationalError
	DataError = sqlite3.DataError

	@staticmethod
	def is_deadlocked(e: sqlite3.Error) -> bool:
		return "database is locked" in str(e)

	@staticmethod
	def is_timedout(e: sqlite3.Error) -> bool:
		return "database is locked" in str(e)

	@staticmethod
	def is_read_only_mode_error(e: sqlite3.Error) -> bool:
		return "attempt to write a readonly database" in str(e)

	@staticmethod
	def is_table_missing(e: sqlite3.Error) -> bool:
		return "no such table" in str(e)

	@staticmethod
	def is_missing_column(e: sqlite3.Error) -> bool:
		return "no such column" in str(e)

	@staticmethod
	def is_duplicate_fieldname(e: sqlite3.Error) -> bool:
		return "duplicate column name" in str(e)

	@staticmethod
	def is_duplicate_entry(e: sqlite3.Error) -> bool:
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_access_denied(e: sqlite3.Error) -> bool:
		return "access denied" in str(e)

	@staticmethod
	def cant_drop_field_or_key(e: sqlite3.Error) -> bool:
		return "cannot drop" in str(e)

	@staticmethod
	def is_syntax_error(e: sqlite3.Error) -> bool:
		return "syntax error" in str(e)

	@staticmethod
	def is_statement_timeout(e: sqlite3.Error) -> bool:
		return "statement timeout" in str(e)

	@staticmethod
	def is_data_too_long(e: sqlite3.Error) -> bool:
		return "string or blob too big" in str(e)

	@staticmethod
	def is_db_table_size_limit(e: sqlite3.Error) -> bool:
		return "too many columns" in str(e)

	@staticmethod
	def is_primary_key_violation(e: sqlite3.IntegrityError) -> bool:
		if hasattr(e, "sqlite_errorcode"):
			return e.sqlite_errorcode == 1555
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_unique_key_violation(e: sqlite3.IntegrityError) -> bool:
		if hasattr(e, "sqlite_errorcode"):
			return e.sqlite_errorcode == 2067
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_interface_error(e: sqlite3.Error):
		return isinstance(e, sqlite3.InterfaceError)

	@staticmethod
	def is_nested_transaction_error(e: sqlite3.Error):
		return "cannot start a transaction within a transaction" in str(e)


class SQLiteDatabase(SQLiteExceptionUtil, Database):
	REGEX_CHARACTER = "regexp"
	default_port = None
	MAX_ROW_SIZE_LIMIT = None

	def get_connection(self, read_only: bool = False):
		conn = self.create_connection(read_only)
		conn.isolation_level = None
		conn.create_function("regexp", 2, regexp)
		pragmas = {
			"journal_mode": "WAL",
			"synchronous": "NORMAL",
		}
		cursor = conn.cursor()
		for pragma, value in pragmas.items():
			cursor.execute(f"PRAGMA {pragma}={value}")
		cursor.close()
		return conn

	def create_connection(self, read_only: bool = False):
		db_path = self.get_db_path()
		sqlite3.register_converter("timestamp", lambda x: datetime.fromisoformat(x.decode()))
		sqlite3.register_converter("date", lambda x: date.fromisoformat(x.decode()))
		sqlite3.register_converter("time", lambda x: time.fromisoformat(x.decode()))
		if read_only:
			return sqlite3.connect(
				f"file:{db_path}?mode=ro",
				uri=True,
				detect_types=sqlite3.PARSE_DECLTYPES,
				timeout=15,
			)
		return sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=15)

	def get_db_path(self):
		return Path(frappe.get_site_path()) / "db" / f"{self.cur_db_name}.db"

	def set_execution_timeout(self, seconds: int):
		self.sql(f"PRAGMA busy_timeout = {int(seconds) * 1000}")

	def setup_type_map(self):
		self.db_type = "sqlite"
		self.type_map = {
			"Currency": ("REAL", None),
			"Int": ("INTEGER", None),
			"Long Int": ("INTEGER", None),
			"Float": ("REAL", None),
			"Percent": ("REAL", None),
			"Check": ("INTEGER", None),
			"Small Text": ("TEXT", None),
			"Long Text": ("TEXT", None),
			"Code": ("TEXT", None),
			"Text Editor": ("TEXT", None),
			"Markdown Editor": ("TEXT", None),
			"HTML Editor": ("TEXT", None),
			"Date": ("DATE", None),
			"Datetime": ("TIMESTAMP", None),
			"Time": ("TIME", None),
			"Text": ("TEXT", None),
			"Data": ("TEXT", None),
			"Link": ("TEXT", None),
			"Dynamic Link": ("TEXT", None),
			"Password": ("TEXT", None),
			"Select": ("TEXT", None),
			"Rating": ("REAL", None),
			"Read Only": ("TEXT", None),
			"Attach": ("TEXT", None),
			"Attach Image": ("TEXT", None),
			"Signature": ("TEXT", None),
			"Color": ("TEXT", None),
			"Barcode": ("TEXT", None),
			"Geolocation": ("TEXT", None),
			"Duration": ("REAL", None),
			"Icon": ("TEXT", None),
			"Phone": ("TEXT", None),
			"Autocomplete": ("TEXT", None),
			"JSON": ("TEXT", None),
		}

	def get_database_size(self):
		"""Return database size in MB."""
		import os

		return os.path.getsize(self.get_db_path()) / (1024 * 1024)

	def _clean_up(self):
		pass

	@staticmethod
	def escape(s, percent=True):
		"""Escape quotes and percent in given string."""
		s = s.replace("'", "''")
		if percent:
			s = s.replace("%", "%%")
		return "'" + s + "'"

	@staticmethod
	def is_type_number(code):
		return code in (sqlite3.NUMERIC, sqlite3.INTEGER, sqlite3.REAL)

	@staticmethod
	def is_type_datetime(code):
		return code == sqlite3.TEXT

	def rename_table(self, old_name: str, new_name: str) -> list | tuple:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		return self.sql(f"ALTER TABLE `{old_name}` RENAME TO `{new_name}`")

	def describe(self, doctype: str) -> list | tuple:
		table_name = get_table_name(doctype)
		return self.sql(f"PRAGMA table_info(`{table_name}`)")

	def change_column_type(
		self, doctype: str, column: str, type: str, nullable: bool = False
	) -> list | tuple:
		"""Change column type by recreating the table"""
		table_name = get_table_name(doctype)
		temp_table = f"{table_name}_new"

		# Get current table column definitions
		columns = []
		column_exists = False
		for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1):
			if col["name"] == column:
				column_exists = True
				null_str = "" if nullable else " NOT NULL"
				columns.append(f"`{col['name']}` {type}{null_str}")
			else:
				null_str = "" if col["notnull"] == 0 else " NOT NULL"
				columns.append(f"`{col['name']}` {col['type']}{null_str}")

		# Check that the column exists
		if not column_exists:
			raise frappe.InvalidColumnName(f"Column {column} does not exist in table {table_name}")

		# Create new table
		create_table = f"CREATE TABLE `{temp_table}` (\n{','.join(columns)}\n)"
		self.sql_ddl(create_table)

		# Copy data
		column_names = [
			f"`{col['name']}`" for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		]
		column_list = ", ".join(column_names)
		self.sql_ddl(f"INSERT INTO `{temp_table}` SELECT {column_list} FROM `{table_name}`")

		# Drop old table and rename new table
		self.sql_ddl(f"DROP TABLE `{table_name}`")
		self.sql_ddl(f"ALTER TABLE `{temp_table}` RENAME TO `{table_name}`")

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		"""Rename column by recreating the table"""
		table_name = get_table_name(doctype)
		temp_table = f"{table_name}_new"

		# Get current table column definitions
		columns = []
		column_exists = False
		for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1):
			if col["name"] == old_column_name:
				column_exists = True
				null_str = "" if col["notnull"] == 0 else " NOT NULL"
				columns.append(f"`{new_column_name}` {col['type']}{null_str}")
			else:
				null_str = "" if col["notnull"] == 0 else " NOT NULL"
				columns.append(f"`{col['name']}` {col['type']}{null_str}")

		if not column_exists:
			raise frappe.InvalidColumnName(f"Column {old_column_name} does not exist in table {table_name}")

		# Create new table
		create_table = f"CREATE TABLE `{temp_table}` (\n{','.join(columns)}\n)"
		self.sql_ddl(create_table)

		# Get list of columns for SELECT, replacing old name with new
		column_names = []
		for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1):
			if col["name"] == old_column_name:
				column_names.append(f"`{old_column_name}` as `{new_column_name}`")
			else:
				column_names.append(f"`{col['name']}`")

		# Copy data
		column_list = ", ".join(column_names)
		self.sql_ddl(f"INSERT INTO `{temp_table}` SELECT {column_list} FROM `{table_name}`")

		# Drop old table and rename new table
		self.sql_ddl(f"DROP TABLE `{table_name}`")
		self.sql_ddl(f"ALTER TABLE `{temp_table}` RENAME TO `{table_name}`")

	def create_auth_table(self):
		self.sql_ddl(
			"""CREATE TABLE IF NOT EXISTS `__Auth` (
				`doctype` TEXT NOT NULL,
				`name` TEXT NOT NULL,
				`fieldname` TEXT NOT NULL,
				`password` TEXT NOT NULL,
				`encrypted` INTEGER NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			)"""
		)

	def create_global_search_table(self):
		if "__global_search" not in self.get_tables():
			self.sql(
				"""CREATE VIRTUAL TABLE __global_search USING FTS5(
				doctype,
				name,
				title,
				content,
				route,
				published
				)"""
			)

	def create_user_settings_table(self):
		self.sql_ddl(
			"""CREATE TABLE IF NOT EXISTS __UserSettings (
			`user` TEXT NOT NULL,
			`doctype` TEXT NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			)"""
		)

	@staticmethod
	def get_on_duplicate_update():
		return "ON CONFLICT DO UPDATE SET "

	def get_table_columns_description(self, table_name):
		"""Return list of columns with descriptions."""
		return self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)

	def get_column_type(self, doctype, column):
		"""Return column type from database."""
		table_name = get_table_name(doctype)
		result = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		for row in result:
			if row["name"] == column:
				return row["type"]
		return None

	def has_index(self, table_name, index_name):
		return self.sql(f"SELECT * FROM pragma_index_list(`{table_name}`) WHERE name = '{index_name}'")

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False) -> frappe._dict | None:
		"""Check if column exists for a specific fields in specified order."""
		indexes = self.sql(f"PRAGMA index_list(`{table_name}`)", as_dict=True)
		for index in indexes:
			index_info = self.sql(f"PRAGMA index_info(`{index['name']}`)", as_dict=True)
			if index_info and index_info[0]["name"] == fieldname:
				return index

	def add_index(self, doctype: str, fields: list, index_name: str | None = None):
		"""Creates an index with given fields if not already created."""

		from frappe.custom.doctype.property_setter.property_setter import (
			make_property_setter,
		)

		# We can't specify the length of the index in SQLite
		fields = [re.sub(r"\(.*?\)", "", field) for field in fields]

		index_name = index_name or self.get_index_name(fields)
		table_name = get_table_name(doctype)
		self.commit()
		self.sql(f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}` ({', '.join(fields)})")

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
		"""Creates unique constraint on fields."""
		if isinstance(fields, str):
			fields = [fields]
		if not constraint_name:
			constraint_name = f"unique_{'_'.join(fields)}"
		table_name = get_table_name(doctype)

		columns = ", ".join(fields)
		sql_create_unique = (
			f"CREATE UNIQUE INDEX IF NOT EXISTS `{constraint_name}` ON `{table_name}` ({columns})"
		)
		self.commit()  # commit before creating index
		self.sql(sql_create_unique)

	def updatedb(self, doctype, meta=None):
		"""Syncs a `DocType` to the table."""
		res = self.sql("SELECT issingle FROM `tabDocType` WHERE name=%s", (doctype,))
		if not res:
			raise Exception(f"Wrong doctype {doctype} in updatedb")

		if not res[0][0]:
			db_table = SQLiteTable(doctype, meta)
			db_table.validate()
			db_table.sync()
			self.commit()

	def get_database_list(self):
		return [self.db_name]

	def get_tables(self, cached=True):
		"""Return list of tables."""
		to_query = not cached

		if cached:
			tables = frappe.cache.get_value("db_tables")
			to_query = not tables

		if to_query:
			tables = self.sql("SELECT name FROM sqlite_master WHERE type='table';", pluck=True)
			frappe.cache.set_value("db_tables", tables)

		return tables

	def get_row_size(self, doctype: str) -> int:
		"""Get estimated max row size of any table in bytes."""
		raise NotImplementedError("SQLite does not support getting row size directly.")

	def execute_query(self, query, values=None):
		query = query.replace("%s", "?")
		try:
			if isinstance(values, dict):
				for k, v in values.items():
					if isinstance(v, str) and "'" in v:
						values[k] = self.escape(v)
					else:
						values[k] = f"'{v}'"
				query = query % values
		except TypeError:
			pass

		return self._cursor.execute(query, values or ())

	def sql(self, *args, **kwargs):
		if args:
			# since tuple is immutable
			args = list(args)
			args[0] = modify_query(args[0])
			args = tuple(args)
		elif kwargs.get("query"):
			kwargs["query"] = modify_query(kwargs.get("query"))

		return super().sql(*args, **kwargs)

	def sql_ddl(self, query, *args, **kwargs):
		"""Execute DDL query."""
		super().sql_ddl(query, *args, **kwargs)
		self.commit()

	def begin(self, *, read_only=False):
		if read_only or frappe.flags.read_only:
			if self._conn:
				self._conn.close()
			self._conn = self.get_connection(read_only=True)
			self._cursor = self._conn.cursor()
			self.read_only = True

		elif hasattr(self, "read_only") and self.read_only:
			self._conn.close()
			self._conn = self.get_connection()
			self._cursor = self._conn.cursor()
			self.read_only = False

		try:
			self.sql("BEGIN")
		except sqlite3.OperationalError as e:
			if not self.is_nested_transaction_error(e):
				raise e

	def commit(self, chain=None):
		"""Commit current transaction. Calls SQL `COMMIT`."""
		if not self._conn:
			self.connect()

		if self._disable_transaction_control:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)
			return

		self.before_rollback.reset()
		self.after_rollback.reset()

		self.before_commit.run()

		self._conn.commit()
		self.transaction_writes = 0
		self.begin()  # explicitly start a new transaction

		self.after_commit.run()

	def rollback(self, *, save_point=None, chain=None):
		"""`ROLLBACK` current transaction. Optionally rollback to a known save_point."""
		if not self._conn:
			self.connect()
		if save_point:
			self.sql(f"rollback to savepoint {save_point}")
		elif not self._disable_transaction_control:
			self.before_commit.reset()
			self.after_commit.reset()

			self.before_rollback.run()

			self._conn.rollback()
			self.begin()

			self.after_rollback.run()
		else:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)

	def get_db_table_columns(self, table) -> list[str]:
		"""Return list of column names from given table."""
		key = f"table_columns::{table}"
		columns = frappe.client_cache.get_value(key)
		if columns is None:
			columns = self.sql(f"PRAGMA table_info(`{table}`)", as_dict=True)
			columns = [col["name"] for col in columns]

			if columns:
				frappe.cache.set_value(key, columns)

		return columns

	def estimate_count(self, doctype: str):
		"""Get estimated count of total rows in a table."""
		from frappe.utils.data import cint

		table = get_table_name(doctype)
		try:
			if count := self.sql(f"SELECT COUNT(*) FROM `{table}`"):
				return cint(count[0][0])
		except sqlite3.OperationalError as e:
			if not self.is_table_missing(e):
				raise
		return 0

	def truncate(self, doctype: str):
		"""Truncate a table."""
		table = get_table_name(doctype)
		self.sql_ddl(f"DELETE FROM `{table}`")
		self.sql_ddl(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

	def check_implicit_commit(self, query: str, query_type: str):
		if query_type in IMPLICIT_COMMIT_QUERY_TYPES and self.transaction_writes:
			raise ImplicitCommitError("This statement can cause implicit commit", query)


def modify_query(query):
	"""
	Modifies query according to the requirements of SQLite
	"""
	# Replace ` with " for definitions
	query = str(query)
	query = query.replace("`", '"')
	query = replace_locate_with_instr(query)

	# Select from requires ""
	if re.search("from tab", query, flags=re.IGNORECASE):
		query = re.sub("from tab([a-zA-Z]*)", r'from "tab\1"', query, flags=re.IGNORECASE)

	return query


def replace_locate_with_instr(query: str) -> str:
	# instr is the locate equivalent in SQLite
	if re.search(r"locate\(", query, flags=re.IGNORECASE):
		query = re.sub(r"locate\(([^,]+),([^)]+)\)", r"instr(\2, \1)", query, flags=re.IGNORECASE)
	return query


def regexp(expr: str, item: str) -> bool:
	"""
	Define regexp implementation for SQLite manually

	Although it works in the CLI - doesn't work through python
	"""
	return re.search(expr, item) is not None
