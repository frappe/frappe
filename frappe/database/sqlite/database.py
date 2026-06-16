import re
import sqlite3
import warnings
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import frappe
from frappe.database.database import (
	TRANSACTION_DISABLED_MSG,
	Database,
	ImplicitCommitError,
)
from frappe.database.sqlite.schema import SQLiteTable
from frappe.utils import get_table_name

_PARAM_COMP = re.compile(r"%\((\w+)\)s")
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


class SQLiteDatabase(SQLiteExceptionUtil, Database):
	REGEX_CHARACTER = "regexp"
	default_port = None
	MAX_ROW_SIZE_LIMIT = None

	# Time (in ms) a connection waits for a write lock held by another connection
	# before giving up with "database is locked". SQLite allows only one writer at a
	# time, so a generous timeout lets concurrent writers queue instead of failing.
	# Override per-site with `sqlite_busy_timeout` in site config.
	DEFAULT_BUSY_TIMEOUT = 30_000

	# Retry `BEGIN IMMEDIATE` a few times if the write lock stays contended.
	WRITE_LOCK_RETRIES = 5

	# Whether the current connection is the read-only (`mode=ro`) connection. Set as a
	# class default so it is always readable even before `connect()`/`begin()` run.
	read_only = False

	@property
	def busy_timeout(self) -> int:
		from frappe.utils.data import cint

		return cint(frappe.conf.get("sqlite_busy_timeout")) or self.DEFAULT_BUSY_TIMEOUT

	def get_connection(self, read_only: bool = False):
		conn = self.create_connection(read_only)
		conn.create_function("regexp", 2, _regexp)
		conn.create_function("regexp_replace", 3, _regexp_replace)
		conn.create_function("now", 0, _now)
		conn.create_function("utc_timestamp", 0, _utc_timestamp)
		conn.create_function("curdate", 0, _curdate)
		conn.create_function("curtime", 0, _curtime)
		conn.create_function("unix_timestamp", -1, _unix_timestamp)
		conn.create_function("timestamp", -1, _timestamp)
		conn.create_function("monthname", 1, _monthname)
		conn.create_function("substring_index", 3, _substring_index)
		conn.create_function("datediff", 2, _datediff)
		conn.create_function("month", 1, _date_part_fn("month"))
		conn.create_function("year", 1, _date_part_fn("year"))
		conn.create_function("day", 1, _date_part_fn("day"))
		conn.create_function("dayofmonth", 1, _date_part_fn("day"))
		conn.create_function("quarter", 1, _quarter)
		conn.create_function("date_format", 2, _date_format)
		conn.create_function("to_seconds", 1, _to_seconds)
		conn.create_function("timediff", 2, _timediff)
		pragmas = {
			"journal_mode": "WAL",
			"synchronous": "NORMAL",
			"busy_timeout": self.busy_timeout,
		}
		cursor = conn.cursor()
		for pragma, value in pragmas.items():
			cursor.execute(f"PRAGMA {pragma}={value}")
		cursor.close()
		return conn

	def create_connection(self, read_only: bool = False):
		db_path = self.get_db_path()
		sqlite3.register_converter("timestamp", _parse_timestamp)
		sqlite3.register_converter("date", _parse_date)
		sqlite3.register_converter("time", _parse_time)
		sqlite3.register_adapter(datetime, lambda v: v.isoformat(sep=" "))
		sqlite3.register_adapter(date, lambda v: v.isoformat())
		sqlite3.register_adapter(time, lambda v: v.isoformat())
		sqlite3.register_adapter(Decimal, lambda v: float(v))
		sqlite3.register_adapter(timedelta, _adapt_timedelta)
		if read_only:
			return sqlite3.connect(
				f"file:{db_path}?mode=ro",
				uri=True,
				detect_types=sqlite3.PARSE_DECLTYPES,
				timeout=self.busy_timeout / 1000,
				isolation_level=None,
			)
		return sqlite3.connect(
			db_path,
			detect_types=sqlite3.PARSE_DECLTYPES,
			timeout=self.busy_timeout / 1000,
			isolation_level=None,
		)

	def get_db_path(self):
		return Path(frappe.get_site_path()) / "db" / f"{self.cur_db_name}.db"

	def set_execution_timeout(self, seconds: int):
		timeout = max(int(seconds) * 1000, self.busy_timeout)
		self._cursor.execute(f"PRAGMA busy_timeout = {timeout}")

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
		s = frappe.as_unicode(s)
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

	def create_sequence_table(self):
		"""Create the `__sequences` table if needed."""
		self.sql_ddl(
			"""CREATE TABLE IF NOT EXISTS `__sequences` (
			name TEXT PRIMARY KEY,
			value INTEGER NOT NULL
			)"""
		)

	def create_sequence(
		self, doctype_name, *, slug="_id_seq", check_not_exists=False, start_value=0, **kwargs
	):
		from frappe import scrub

		sequence_name = scrub(doctype_name + slug)
		# `value` stores the last value handed out; the next `nextval` returns value + 1.
		# Postgres' default start is 1, so a falsy start_value seeds 0 (first nextval = 1).
		initial = start_value - 1 if start_value else 0
		# `DO NOTHING` keeps an existing sequence intact (matches `check_not_exists`).
		self.sql(
			"INSERT INTO `__sequences` (name, value) VALUES (%s, %s) ON CONFLICT(name) DO NOTHING",
			(sequence_name, initial),
		)
		return sequence_name

	def get_next_sequence_val(self, doctype_name, slug="_id_seq"):
		from frappe import scrub

		sequence_name = scrub(f"{doctype_name}{slug}")
		row = self.sql(
			"UPDATE `__sequences` SET value = value + 1 WHERE name = %s RETURNING value",
			(sequence_name,),
		)
		if row:
			return row[0][0]

		# Sequence row missing (e.g. doctype created before SQLite sequence support):
		# seed it from the max existing name so an existing table never reuses an id.
		table = get_table_name(doctype_name)
		max_name = 0
		try:
			res = self.sql(f"SELECT MAX(CAST(name AS INTEGER)) FROM `{table}`")
			max_name = (res and res[0][0]) or 0
		except sqlite3.OperationalError as e:
			if not self.is_table_missing(e):
				raise
		next_val = int(max_name) + 1
		self.sql(
			"INSERT INTO `__sequences` (name, value) VALUES (%s, %s) "
			"ON CONFLICT(name) DO UPDATE SET value = value + 1",
			(sequence_name, next_val),
		)
		return next_val

	def set_next_sequence_val(self, doctype_name, next_val, *, slug="_id_seq", is_val_used=False):
		from frappe import scrub

		sequence_name = scrub(doctype_name + slug)
		# Mirror Postgres SETVAL: if the value was used, the next nextval is next_val + 1.
		stored = next_val if is_val_used else next_val - 1
		self.sql(
			"INSERT INTO `__sequences` (name, value) VALUES (%s, %s) "
			"ON CONFLICT(name) DO UPDATE SET value = excluded.value",
			(sequence_name, stored),
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
		if isinstance(values, dict):
			query, bind = _bind_named_params(query, values)
			return self._cursor.execute(query, bind)

		query, values = _expand_positional_params(query, values)
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

	def connect(self):
		"""Connect, then open the request's transaction (see ``begin``)."""
		super().connect()
		self.begin()

	def _begin_transaction(self):
		"""Open ``BEGIN IMMEDIATE`` for writable connections, ``DEFERRED`` for read-only ones."""
		if self._conn.in_transaction:
			return
		if self.read_only:
			self._cursor.execute("BEGIN DEFERRED")
		else:
			self._begin_immediate()

	def _begin_immediate(self):
		"""Acquire the write lock with ``BEGIN IMMEDIATE``, retrying briefly on contention."""
		import random
		import time

		for attempt in range(self.WRITE_LOCK_RETRIES):
			try:
				self._cursor.execute("BEGIN IMMEDIATE")
				return
			except sqlite3.OperationalError as e:
				if not self.is_deadlocked(e) or attempt == self.WRITE_LOCK_RETRIES - 1:
					raise
				time.sleep(random.uniform(0, 0.05 * (attempt + 1)))

	def begin(self, *, read_only=None):
		"""Switch connection mode if needed, then start its transaction.

		``read_only=None`` keeps the current mode across restarts.
		"""
		if read_only is None:
			read_only = self.read_only
		read_only = read_only or frappe.flags.read_only
		if read_only != self.read_only:
			if self._conn:
				self._conn.close()
			self._conn = self.get_connection(read_only=read_only)
			self._cursor = self._conn.cursor()
			self.read_only = read_only

		if self._conn:
			self._begin_transaction()

	def enter_read_only(self) -> bool:
		"""Switch ``frappe.read_only()`` to the ``mode=ro`` connection when safe.

		Returns ``False`` if already read-only or if writes are pending.
		"""
		if self.read_only or self.transaction_writes:
			return False
		# Reopen the connection in mode=ro, releasing the empty write transaction.
		self.begin(read_only=True)
		return True

	def exit_read_only(self):
		"""Restore the writable connection after ``enter_read_only``."""
		self.begin(read_only=False)

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

		if self._conn.in_transaction:
			self._conn.commit()
		self.transaction_writes = 0
		self.value_cache.clear()
		self.begin()  # restore transaction state (read-only snapshot if applicable)

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

			if self._conn.in_transaction:
				self._conn.rollback()
			self.value_cache.clear()
			self.begin()

			self.after_rollback.run()
		else:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)

	@contextmanager
	def unbuffered_cursor(self):
		"""SQLite reads rows lazily from its single cursor, so there is no separate
		server-side/unbuffered cursor to switch to (unlike MariaDB's SSCursor or
		Postgres' named cursor). Used with ``as_iterator=True`` it already provides
		streaming reads, so this is a no-op context manager for API compatibility."""
		if not self._conn:
			self.connect()
		yield

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
	query = _replace_locate_with_instr(query)
	query = _strip_row_locks(query)
	query = _strip_index_hints(query)
	query = _strip_wrapping_parens(query)
	query = re.sub(
		r"\bcurrent_(date|time|timestamp)\s*\(\s*\)",
		r"current_\1",
		query,
		flags=re.IGNORECASE,
	)
	query = re.sub(r"\bif\s*\(", "iif(", query, flags=re.IGNORECASE)

	# Select from requires ""
	if re.search("from tab", query, flags=re.IGNORECASE):
		query = re.sub("from tab([a-zA-Z]*)", r'from "tab\1"', query, flags=re.IGNORECASE)

	return query


def _strip_wrapping_parens(query: str) -> str:
	"""Unwrap a whole-statement parenthesised SELECT, e.g. ``(SELECT ...)`` -> ``SELECT ...``.

	MariaDB accepts a top-level parenthesised query (ERPNext builds scalar-subquery
	strings this way); SQLite rejects it with ``near "(": syntax error``. Only the
	*outermost* wrapping parens are removed, and only when they enclose the entire
	statement -- so ``(SELECT ...) UNION (SELECT ...)`` is left untouched."""
	stripped = query.strip()
	if not stripped.startswith("("):
		return query

	depth = 0
	for i, ch in enumerate(stripped):
		if ch == "(":
			depth += 1
		elif ch == ")":
			depth -= 1
			if depth == 0:
				# Matched the opening paren. Unwrap only if it closes the whole
				# statement and wraps a SELECT/WITH (not a VALUES list or similar).
				if i == len(stripped) - 1:
					inner = stripped[1:i].strip()
					if inner[:6].lower() == "select" or inner[:4].lower() == "with":
						return inner
				return query
	return query


def _strip_row_locks(query: str) -> str:
	"""Remove row-level locking clauses (`FOR UPDATE`, `LOCK IN SHARE MODE`) that
	MariaDB/Postgres support but SQLite does not.

	SQLite serializes all writers behind a single database-wide write lock (acquired
	via ``BEGIN IMMEDIATE``), so an explicit row lock is redundant -- the rows are
	already protected for the duration of the write transaction. The clause is always
	the final part of a SELECT, so it is safe to strip from the tail."""
	query = re.sub(
		r"\s+for\s+update(\s+nowait|\s+skip\s+locked)?\s*;?\s*$",
		"",
		query,
		flags=re.IGNORECASE,
	)
	query = re.sub(r"\s+lock\s+in\s+share\s+mode\s*;?\s*$", "", query, flags=re.IGNORECASE)
	return query


def _bind_named_params(query: str, values: dict):
	"""Rewrite pyformat ``%(name)s`` placeholders to SQLite ``:name`` placeholders.

	A sequence value is expanded into a parenthesised list so ``WHERE x IN %(names)s``
	works (SQLite can't bind a sequence to one placeholder); an empty sequence becomes
	``(NULL)`` and a nested sequence becomes a row value, supporting ``WHERE (a, b) IN
	%(pairs)s``. The caller's dict is never mutated."""
	bind: dict = {}

	def placeholder(key, value):
		"""Register ``value`` under ``key`` and return its placeholder text, recursing
		into sequences (e.g. ``[1, 2]`` -> ``(:key__0, :key__1)``)."""
		if isinstance(value, list | tuple | set):
			if not value:
				return "(NULL)"
			return "(" + ", ".join(placeholder(f"{key}__{i}", v) for i, v in enumerate(value)) + ")"
		bind[key] = value
		return f":{key}"

	def replace(match):
		key = match.group(1)
		if key not in values:
			return match.group(0)
		return placeholder(key, values[key])

	return _PARAM_COMP.sub(replace, query), bind


def _expand_positional_params(query: str, values):
	"""Translate pyformat ``%s`` placeholders to SQLite ``?`` placeholders, expanding
	any sequence value into ``(?, ?, ...)``.

	MariaDB/Postgres drivers expand a list/tuple bound to a single ``%s`` (the common
	``WHERE name IN %s`` idiom) into a parenthesised list. SQLite's driver cannot bind
	a sequence to one placeholder, so we expand it ourselves and flatten the values to
	match. An empty sequence becomes ``(NULL)`` (matches nothing), mirroring the drivers.
	"""
	if not values:
		return query.replace("%s", "?"), values

	if not isinstance(values, list | tuple):
		values = (values,)

	parts = query.split("%s")
	# One value per placeholder is required. If they don't line up (e.g. a stray `%s`
	# inside a string literal), fall back to the naive rewrite.
	if len(parts) - 1 != len(values):
		return query.replace("%s", "?"), values

	def expand(value):
		"""Return ``(placeholder_text, bound_values)`` for one value, recursing into
		sequences (e.g. ``[1, 2]`` -> ``("(?, ?)", [1, 2])``)."""
		if not isinstance(value, list | tuple | set):
			return "?", [value]
		if not value:
			return "(NULL)", []
		texts, flat = [], []
		for item in value:
			text, sub = expand(item)
			texts.append(text)
			flat.extend(sub)
		return "(" + ", ".join(texts) + ")", flat

	rendered = [parts[0]]
	flat = []
	for value, tail in zip(values, parts[1:], strict=True):
		text, sub = expand(value)
		rendered.append(text)
		flat.extend(sub)
		rendered.append(tail)

	return "".join(rendered), flat


def _strip_index_hints(query: str) -> str:
	"""Remove MariaDB/MySQL optimizer index hints (`FORCE INDEX (...)`, `USE INDEX (...)`,
	`IGNORE INDEX (...)`). SQLite has no index hints -- its query planner chooses indexes
	itself -- and the hint is purely advisory, so dropping it is safe. ERPNext emits these
	via the query builder's ``.force_index()`` as well as in some raw SQL."""
	return re.sub(
		r"\s+(force|use|ignore)\s+index\s*\([^)]*\)",
		" ",
		query,
		flags=re.IGNORECASE,
	)


def _replace_locate_with_instr(query: str) -> str:
	# instr is the locate equivalent in SQLite
	if re.search(r"locate\(", query, flags=re.IGNORECASE):
		query = re.sub(r"locate\(([^,]+),([^)]+)\)", r"instr(\2, \1)", query, flags=re.IGNORECASE)
	return query


def _now() -> str:
	"""MariaDB/Postgres ``NOW()`` -- current datetime in frappe's stored format."""
	from frappe.utils import now

	return now()


def _utc_timestamp() -> str:
	"""MariaDB ``UTC_TIMESTAMP()`` -- current UTC datetime."""
	return datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _curdate() -> str:
	"""MariaDB ``CURDATE()`` -- current date."""
	from frappe.utils import nowdate

	return nowdate()


def _curtime() -> str:
	"""MariaDB ``CURTIME()`` -- current time."""
	from frappe.utils import nowtime

	return nowtime()


def _parse_timestamp(value: bytes):
	"""Tolerant DATETIME converter. SQLite is dynamically typed, so a column declared
	as a timestamp may hold a non-strict-ISO value; fall back to frappe's lenient
	parser, and finally to the raw string, rather than raising."""
	s = value.decode()
	try:
		return datetime.fromisoformat(s)
	except ValueError:
		from frappe.utils import get_datetime

		try:
			return get_datetime(s)
		except Exception:
			return s


def _parse_date(value: bytes):
	"""Tolerant DATE converter -- handles values that carry a time component (e.g. a
	datetime stored in a DATE-declared column) by extracting the date part."""
	s = value.decode()
	try:
		return date.fromisoformat(s)
	except ValueError:
		from frappe.utils import getdate

		try:
			return getdate(s)
		except Exception:
			return s


def _adapt_timedelta(td: timedelta) -> str:
	"""Serialize a `timedelta` back to a ``HH:MM:SS[.ffffff]`` TIME string (the inverse
	of `_parse_time`), so a value read from a TIME column can be re-bound as a param."""
	total = int(td.total_seconds())
	hours, rem = divmod(total, 3600)
	minutes, seconds = divmod(rem, 60)
	if td.microseconds:
		return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{td.microseconds:06d}"
	return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_time(value: bytes):
	"""Parse a stored TIME into a `timedelta`, matching how MariaDB's driver surfaces
	TIME columns (which frappe/ERPNext expect). Tolerant of non-zero-padded values and
	of datetime values landing in a TIME-declared column."""
	s = value.decode()
	try:
		t = time.fromisoformat(s)
	except ValueError:
		from frappe.utils import get_time

		try:
			t = get_time(s)
		except Exception:
			return s
	return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)


# MariaDB DATE_FORMAT specifiers that differ from Python strftime.
_DATE_FORMAT_MAP = {
	"%i": "%M",  # minutes
	"%s": "%S",  # seconds
	"%M": "%B",  # full month name
	"%h": "%I",  # 12-hour
	"%W": "%A",  # full weekday name
	"%r": "%I:%M:%S %p",
	"%T": "%H:%M:%S",
}


def _date_format(value, fmt) -> str | None:
	"""MariaDB ``DATE_FORMAT(date, fmt)`` using Python ``strftime`` with the MariaDB
	format specifiers that differ from strftime translated. Done in a single pass so a
	translated token (e.g. ``%i`` -> ``%M``) is not re-translated by a later rule."""
	if value is None or fmt is None:
		return None
	from frappe.utils import get_datetime

	translated = re.sub(r"%.", lambda m: _DATE_FORMAT_MAP.get(m.group(0), m.group(0)), fmt)
	return get_datetime(value).strftime(translated)


def _datediff(date1, date2) -> int | None:
	"""MariaDB ``DATEDIFF(date1, date2)`` -- whole days between the two dates."""
	if date1 is None or date2 is None:
		return None
	from frappe.utils import getdate

	return (getdate(date1) - getdate(date2)).days


def _date_part_fn(part: str):
	"""Build a scalar function returning a date part (``MONTH``/``YEAR``/``DAY``)."""

	def fn(value):
		if value is None:
			return None
		from frappe.utils import getdate

		return getattr(getdate(value), part)

	return fn


def _quarter(value) -> int | None:
	"""MariaDB ``QUARTER(date)`` -- 1-4."""
	if value is None:
		return None
	from frappe.utils import getdate

	return (getdate(value).month - 1) // 3 + 1


def _monthname(value) -> str | None:
	"""MariaDB ``MONTHNAME(date)`` -- full month name (e.g. 'January')."""
	if value is None:
		return None
	from frappe.utils import getdate

	return getdate(value).strftime("%B")


def _substring_index(value, delim, count) -> str | None:
	"""MariaDB ``SUBSTRING_INDEX(str, delim, count)``: return the substring before the
	``count``-th occurrence of ``delim`` (from the left if positive, right if negative)."""
	if value is None:
		return None
	value = str(value)
	count = int(count)
	if count == 0:
		return ""
	if count > 0:
		return delim.join(value.split(delim)[:count])
	return delim.join(value.split(delim)[count:])


def _timestamp(*args) -> str | None:
	"""MariaDB ``TIMESTAMP(expr)`` / ``TIMESTAMP(date, time)``: with two arguments,
	combine a date and time into a datetime; with one, return it as a datetime string.
	Combining by concatenation is sufficient for frappe's ISO `YYYY-MM-DD` / `HH:MM:SS`
	values and preserves lexicographic ordering."""
	args = [a for a in args if a is not None]
	if not args:
		return None
	if len(args) == 1:
		return str(args[0])
	return f"{args[0]} {args[1]}"


def _to_seconds(value) -> int | None:
	"""MariaDB ``TO_SECONDS(expr)`` -- seconds since year 0. The absolute epoch is
	irrelevant in practice (it is used in differences, ``TO_SECONDS(a) - TO_SECONDS(b)``),
	so seconds since the Unix epoch gives identical deltas while staying integer."""
	if value is None:
		return None
	from frappe.utils import get_datetime

	return int(get_datetime(value).timestamp())


def _unix_timestamp(*args) -> int | float:
	"""MariaDB ``UNIX_TIMESTAMP([datetime])`` -- epoch seconds.

	With no argument returns the current epoch; with a datetime/date string
	argument returns that moment's epoch (matching MariaDB's overloads). MariaDB
	returns an integer for whole-second values (and a decimal only when the input
	carries fractional seconds), so mirror that rather than always returning a float."""
	from frappe.utils import get_datetime

	epoch = datetime.now().timestamp() if not args or args[0] is None else get_datetime(args[0]).timestamp()
	return int(epoch) if epoch == int(epoch) else epoch


def _timediff(t1, t2) -> float | None:
	"""Return seconds difference; 0.0 when equal (falsy), unlike SQLite's built-in timediff() which returns a string."""
	if t1 is None or t2 is None:
		return None
	try:

		def _parse(s):
			s = str(s).strip()
			for fmt in (
				"%Y-%m-%d %H:%M:%S.%f",
				"%Y-%m-%d %H:%M:%S",
				"%Y-%m-%dT%H:%M:%S.%f",
				"%Y-%m-%dT%H:%M:%S",
			):
				try:
					return datetime.strptime(s, fmt)
				except ValueError:
					continue
			return None

		d1, d2 = _parse(t1), _parse(t2)
		if d1 is None or d2 is None:
			return None
		return (d1 - d2).total_seconds()
	except Exception:
		return None


def _regexp(expr: str, item: str) -> bool:
	"""
	Define regexp implementation for SQLite manually

	Although it works in the CLI - doesn't work through python
	"""
	return re.search(expr, item) is not None


def _regexp_replace(item: str, pattern: str, repl: str) -> str:
	"""
	Define regexp_replace implementation for SQLite
	"""
	return re.sub(pattern, repl, item)
