import logging
import re
import sqlite3
import typing
import warnings
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.dialects.mysql import MySQL as _MySQLDialect
from sqlglot.dialects.sqlite import SQLite as _SQLiteDialect

import frappe
from frappe.database.database import (
	TRANSACTION_DISABLED_MSG,
	Database,
	ImplicitCommitError,
)
from frappe.database.sqlite.schema import SQLiteTable
from frappe.utils import get_table_name

# sqlglot warns for every construct its target dialect can't represent (e.g. FOR UPDATE, which
# modify_query() relies on it silently dropping) -- mute our own use without touching global config.
_sqlglot_logger = logging.getLogger("sqlglot")
_sqlglot_logger.addHandler(logging.NullHandler())
_sqlglot_logger.propagate = False

_PARAM_COMP = re.compile(r"%\((\w+)\)s")
# A single-quoted string literal, including any doubled '' escapes inside it. Used to skip
# literals when rewriting placeholders, so a literal that contains "%s" (e.g. `LIKE '%system%'`)
# is never mistaken for a bind placeholder.
_SINGLE_QUOTE_LITERAL = re.compile(r"'(?:[^']|'')*'")
IMPLICIT_COMMIT_QUERY_TYPES = frozenset(("start", "alter", "drop", "create", "truncate"))


class SequenceGeneratorLimitExceeded(sqlite3.Error):
	"""Raised when an emulated sequence with a max_value (and no cycle) is exhausted.

	SQLite has no native sequences (frappe emulates them, see
	``frappe.database.sequence``), so unlike MariaDB/Postgres there is no driver
	exception to reuse for this case.
	"""


def _split_sql_literals(query: str):
	"""Yield ``(is_literal, chunk)`` over ``query``: ``is_literal`` chunks are single-quoted
	string literals (quotes included) that must not be scanned for placeholders; the rest is the
	SQL around them."""
	pos = 0
	for m in _SINGLE_QUOTE_LITERAL.finditer(query):
		if m.start() > pos:
			yield False, query[pos : m.start()]
		yield True, m.group(0)
		pos = m.end()
	if pos < len(query):
		yield False, query[pos:]


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
	SequenceGeneratorLimitExceeded = SequenceGeneratorLimitExceeded

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
		from frappe.database.sqlite import functions
		from frappe.utils import now, nowdate, nowtime

		conn = self.create_connection(read_only)
		# Disable the "double-quoted string literal" misfeature. frappe only ever emits
		# double-quotes as identifiers (backticks are rewritten to double-quotes; string
		# literals use single quotes), so an unknown double-quoted name is a bug -- e.g. an
		# invalid link fieldname -- and should error "no such column" instead of silently
		# being treated as a string literal that matches nothing.
		conn.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DDL, False)
		conn.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML, False)
		conn.create_function("now", 0, now)
		conn.create_function("curdate", 0, nowdate)
		conn.create_function("curtime", 0, nowtime)
		conn.create_function("regexp", 2, functions.regexp)
		conn.create_function("regexp_replace", 3, functions.regexp_replace)
		conn.create_function("utc_timestamp", 0, functions.utc_timestamp)
		conn.create_function("unix_timestamp", -1, functions.unix_timestamp)
		conn.create_function("timestamp", -1, functions.timestamp)
		conn.create_function("to_seconds", 1, functions.to_seconds)
		conn.create_function("timediff", 2, functions.timediff)
		conn.create_function("datediff", 2, functions.datediff)
		conn.create_function("date_format", 2, functions.date_format)
		conn.create_function("monthname", 1, functions.monthname)
		conn.create_function("quarter", 1, functions.quarter)
		conn.create_function("substring_index", 3, functions.substring_index)
		conn.create_function("month", 1, functions.date_part("month"))
		conn.create_function("year", 1, functions.date_part("year"))
		conn.create_function("day", 1, functions.date_part("day"))
		conn.create_function("dayofmonth", 1, functions.date_part("day"))
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
		from frappe.database.sqlite import functions

		db_path = self.get_db_path()
		# Columns are declared DATETIME (see SQLiteTable.create); register that name too so
		# PARSE_DECLTYPES surfaces datetime objects -- matching MariaDB -- instead of raw strings.
		sqlite3.register_converter("datetime", functions.converter_datetime)
		sqlite3.register_converter("timestamp", functions.converter_datetime)
		sqlite3.register_converter("date", functions.converter_date)
		sqlite3.register_converter("time", functions.converter_time)
		# No REAL converter: _transform_result / fetch_as_dict round all floats to 9dp,
		# covering both REAL-declared columns and float values from computed expressions.
		sqlite3.register_adapter(datetime, functions.adapter_datetime)
		sqlite3.register_adapter(date, functions.adapter_date)
		sqlite3.register_adapter(time, functions.adapter_time)
		sqlite3.register_adapter(Decimal, functions.adapter_decimal)
		sqlite3.register_adapter(timedelta, functions.adapter_timedelta)
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

	def _transform_result(self, result):
		"""Convert list of rows to tuple-of-tuples (PyMySQL compat) and round floats to 9dp."""
		return tuple(tuple(round(v, 9) if type(v) is float else v for v in row) for row in result)

	def fetch_as_dict(self, result):
		"""Build _dict rows, strip double-quotes from string-literal column names, and round floats to 9dp."""
		if not result:
			return []
		keys = []
		for col in self._cursor.description:
			name = col[0]
			if name.startswith('"') and name.endswith('"') and len(name) > 2:
				name = name[1:-1]
			keys.append(name)
		return [
			frappe._dict(
				{k: (round(v, 9) if type(v) is float else v) for k, v in zip(keys, row, strict=False)}
			)
			for row in result
		]

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
		cols = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		if not any(col["name"] == column for col in cols):
			raise frappe.InvalidColumnName(f"Column {column} does not exist in table {table_name}")

		column_defs = []
		for col in cols:
			if col["name"] == column:
				null_str = "" if nullable else " NOT NULL"
				column_defs.append(f"`{col['name']}` {type}{null_str}")
			else:
				null_str = "" if col["notnull"] == 0 else " NOT NULL"
				column_defs.append(f"`{col['name']}` {col['type']}{null_str}")

		select_columns = [f"`{col['name']}`" for col in cols]
		self._rebuild_table(table_name, column_defs, select_columns)

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		"""Rename column by recreating the table"""
		table_name = get_table_name(doctype)
		cols = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		if not any(col["name"] == old_column_name for col in cols):
			raise frappe.InvalidColumnName(f"Column {old_column_name} does not exist in table {table_name}")

		column_defs = []
		select_columns = []
		for col in cols:
			null_str = "" if col["notnull"] == 0 else " NOT NULL"
			if col["name"] == old_column_name:
				column_defs.append(f"`{new_column_name}` {col['type']}{null_str}")
				select_columns.append(f"`{old_column_name}` as `{new_column_name}`")
			else:
				column_defs.append(f"`{col['name']}` {col['type']}{null_str}")
				select_columns.append(f"`{col['name']}`")

		self._rebuild_table(table_name, column_defs, select_columns)

	def _rebuild_table(self, table_name: str, column_defs: list[str], select_columns: list[str]) -> None:
		"""Recreate `table_name` with `column_defs`, copying data via `select_columns`, then swap it in."""
		temp_table = f"{table_name}_new"
		self.sql_ddl(f"CREATE TABLE `{temp_table}` (\n{','.join(column_defs)}\n)")
		self.sql_ddl(f"INSERT INTO `{temp_table}` SELECT {', '.join(select_columns)} FROM `{table_name}`")
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
		# SQLite has no native sequences; this table emulates them for
		# autoname:autoincrement doctypes. See frappe.database.sequence.
		from frappe.database.sequence import SQLITE_SEQUENCE_TABLE

		# `declared` is 1 for sequences defined via create_sequence and 0 for rows
		# auto-created by naming/set_next_val; it lets create_sequence adopt an
		# implicit row without ever overwriting an explicit definition.
		self.sql_ddl(
			f"""CREATE TABLE IF NOT EXISTS `{SQLITE_SEQUENCE_TABLE}` (
			`name` TEXT PRIMARY KEY,
			`current` INTEGER NOT NULL,
			`increment` INTEGER NOT NULL DEFAULT 1,
			`min_value` INTEGER NOT NULL DEFAULT 1,
			`max_value` INTEGER,
			`cycle` INTEGER NOT NULL DEFAULT 0,
			`declared` INTEGER NOT NULL DEFAULT 0
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

	def add_index(
		self, doctype: str, fields: list, index_name: str | None = None, using=None, where=None, include=None
	):
		"""Creates an index with given fields if not already created.
		`using`/`where`/`include` are postgres-only (trigram/partial/covering); a `using` kind
		has no SQLite equivalent so it is skipped, and a plain index covers all rows regardless of
		`where`/`include`."""

		from frappe.custom.doctype.property_setter.property_setter import (
			make_property_setter,
		)

		if using:
			return
		# We can't specify the length of the index in SQLite
		fields = [re.sub(r"\(.*?\)", "", field) for field in fields]

		index_name = index_name or self.get_index_name(fields)
		table_name = get_table_name(doctype)
		self.commit()
		self.sql(f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}` ({', '.join(fields)})")

		# Ensure that DB migration doesn't clear this index, assuming this is manually added
		# via code or console. Text-like fieldtypes can't carry a search_index flag (doctype
		# validation rejects it), though the TEXT column above is still validly indexed.
		if len(fields) == 1 and not (frappe.flags.in_install or frappe.flags.in_migrate):
			field = frappe.get_meta(doctype).get_field(fields[0])
			if field and field.fieldtype not in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
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

	@staticmethod
	def format_datetime(value):
		"""Use isoformat(sep=" ") to match how SQLite stores datetimes; base class always appends microseconds which misses rows stored without them."""
		from frappe.database.utils import FallBackDateTimeStr
		from frappe.utils import get_datetime

		if not value:
			return FallBackDateTimeStr
		return get_datetime(value).isoformat(sep=" ")

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
		# Open the transaction lazily on the first statement (still BEGIN IMMEDIATE for
		# writable connections) so the write lock isn't held idle between transactions.
		if self._conn is not None and not self._conn.in_transaction:
			self._begin_transaction()

		if isinstance(values, dict):
			query, bind = _bind_named_params(query, values)
			return self._cursor.execute(query, bind)

		query, values = _expand_positional_params(query, values)
		return self._cursor.execute(query, values or ())

	def sql(self, *args, **kwargs):
		# The query builder (see query_builder/builder.py) already emits SQLite-dialect SQL, so
		# it sets _skip_dialect_rewrite to bypass modify_query -- re-transpiling that output would
		# be wasteful and lossy. Only raw MariaDB-flavoured SQL (frappe.db.sql) needs rewriting.
		if not kwargs.pop("_skip_dialect_rewrite", False):
			if args:
				# args is a tuple (immutable); rebuild it with the query rewritten.
				args = (modify_query(args[0]), *args[1:])
			elif kwargs.get("query"):
				kwargs["query"] = modify_query(kwargs["query"])

		return super().sql(*args, **kwargs)

	def log_query(self, query, query_type, values=None, debug=False):
		# The base class doesn't set last_query; MariaDB/Postgres do (via override /
		# property). Capture it here too so tooling that reads frappe.db.last_query
		# (e.g. the recorder) works on SQLite.
		mogrified_query = super().log_query(query, query_type, values, debug)
		self.last_query = mogrified_query
		return mogrified_query

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
		# A read-only scope (frappe.read_only()) must not grab the write lock even when it couldn't
		# swap to the mode=ro connection (e.g. writes were already pending): a DEFERRED read is
		# served concurrently under WAL, so it won't deadlock against a writer.
		if self.read_only or frappe.flags.read_only:
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

		# Transaction is opened lazily by execute_query() on the first statement, not
		# here, so the write lock is not held during idle periods between transactions.

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
		# A transaction boundary ends any read-only scope (e.g. a query report that did
		# begin(read_only=True)); return to the writable connection unless the whole site
		# is in read-only mode (begin() still honours frappe.flags.read_only).
		self.begin(read_only=False)

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
			# See commit(): a transaction boundary ends any read-only scope.
			self.begin(read_only=False)

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
		# SQLite runs DDL (ALTER/CREATE/DROP/TRUNCATE) inside the current transaction and rolls it
		# back with everything else -- unlike MariaDB/Postgres it does not implicitly commit -- so
		# these statements are safe mid-transaction (e.g. renaming a doctype's table).
		pass


# ---------------------------------------------------------------------------
# modify_query() rewrites a MariaDB-flavoured SQL string for SQLite compatibility.
# It parses the query into an AST with sqlglot (reading the MariaDB/MySQL dialect
# frappe's query builder and raw SQL are written in) and regenerates it for SQLite.
# That alone handles backtick->doublequote quoting, dropping `FOR UPDATE`/`LOCK IN
# SHARE MODE`/index hints, and `IF(...)` -> `IIF(...)`. A handful of AST passes on
# top handle rewrites sqlglot has no dialect-conversion rule for: frappe's
# NOW()/CURRENT_TIMESTAMP +/- INTERVAL idiom, ORDER BY collation, and HAVING alias
# resolution (see each pass below for why SQLite needs it).
#
# DDL/PRAGMA statements skip the parser entirely: frappe already writes these in
# SQLite-native SQL (see schema.py), so only backtick quoting applies, and it's
# cheaper besides -- these run far less often than DML.
# ---------------------------------------------------------------------------

_DML_KEYWORDS = ("select", "update", "delete", "insert", "with")


def _is_dml(query: str) -> bool:
	"""Whether ``query`` opens with a DML keyword (optionally through leading whitespace/parens,
	e.g. a whole-statement-wrapped ``(SELECT ...)``)."""
	return query.lstrip(" \t\r\n(").lower().startswith(_DML_KEYWORDS)


_INTERVAL_UNITS = {
	"year": "years",
	"years": "years",
	"month": "months",
	"months": "months",
	"week": "days",
	"weeks": "days",
	"day": "days",
	"days": "days",
	"hour": "hours",
	"hours": "hours",
	"minute": "minutes",
	"minutes": "minutes",
	"second": "seconds",
	"seconds": "seconds",
}


def _render_placeholder(self, node: exp.Placeholder) -> str:
	"""Render a masked placeholder back to frappe's pyformat style (see _mask_placeholders)."""
	name = node.this
	return f"%({name})s" if name else "%s"


class _FrappeMySQL(_MySQLDialect):
	"""MariaDB/MySQL dialect that reads both backtick- and doublequote-quoted names as
	identifiers, never as string literals.

	Raw SQL frappe hands to modify_query is MariaDB-flavoured (backtick identifiers), but SQL
	built by the query builder (`query_builder/builder.py`) already targets SQLite and quotes
	identifiers with double quotes -- standard MySQL grammar treats those as string literals
	(only backtick is an identifier quote), which would silently turn every quoted column/table
	name in query-builder SQL into a string constant. Accepting both matches how frappe actually
	writes SQL; frappe never emits a genuine double-quoted string literal (values are always
	bound as parameters or single-quoted), so there is no ambiguity to resolve here."""

	class Tokenizer(_MySQLDialect.Tokenizer):
		IDENTIFIERS: typing.ClassVar = ["`", '"']
		QUOTES: typing.ClassVar = ["'"]


def _render_regexp(self, node: exp.RegexpLike) -> str:
	"""Render as SQLite's native ``X REGEXP Y`` operator, not the default ``REGEXP_LIKE(x, y)``
	rendering: SQLite has no such function, only the ``REGEXP`` operator, which it dispatches to
	a user-defined function named ``regexp`` -- the one this module registers on every
	connection (``get_connection``)."""
	return f"{self.sql(node, 'this')} REGEXP {self.sql(node, 'expression')}"


class _FrappeSQLite(_SQLiteDialect):
	"""SQLite dialect that emits pyformat placeholders instead of `:name`/`?`, and the native
	``REGEXP`` operator instead of ``REGEXP_LIKE(...)``."""

	class Generator(_SQLiteDialect.Generator):
		TRANSFORMS: typing.ClassVar = {
			**_SQLiteDialect.Generator.TRANSFORMS,
			exp.Placeholder: _render_placeholder,
			exp.RegexpLike: _render_regexp,
		}


def _mask_placeholders(query: str) -> str:
	"""Rewrite pyformat placeholders to syntax sqlglot's parser accepts as a bind parameter:
	``%(name)s`` -> ``:name``, ``%s`` -> ``?``. ``_render_placeholder`` converts them back
	when generating, via the AST rather than a second text substitution -- a blind
	``:name``/``?`` -> pyformat regex on the output would also match colons or question
	marks that legitimately appear inside string literals (e.g. a bound time value '12:30:00'
	rendered as a literal elsewhere in the query).

	Only placeholders *outside* single-quoted string literals are rewritten, so a literal that
	happens to contain ``%s`` -- e.g. ``LIKE '%system%'`` -- is left untouched."""

	def mask(chunk: str) -> str:
		return _PARAM_COMP.sub(r":\1", chunk).replace("%s", "?")

	return "".join(chunk if is_literal else mask(chunk) for is_literal, chunk in _split_sql_literals(query))


def _unwrap_top_level_subquery(tree: exp.Expression) -> exp.Expression:
	"""Unwrap a whole-statement parenthesised SELECT, e.g. ``(SELECT ...)`` -> ``SELECT ...``.

	MariaDB accepts a top-level parenthesised query (ERPNext builds scalar-subquery strings
	this way); SQLite rejects it with ``near "(": syntax error``. sqlglot parses this shape as
	a bare ``Subquery`` node only when the parens wrap the *entire* statement, so this never
	touches ``(SELECT ...) UNION (SELECT ...)`` (parsed as a `Union` of two `Subquery` operands)."""
	if not isinstance(tree, exp.Subquery):
		return tree
	# Don't unwrap if the wrapper carries its own ORDER BY / LIMIT / OFFSET (e.g.
	# `(SELECT ... ORDER BY x LIMIT 5)`) -- those live on the Subquery node and would be dropped.
	if any(tree.args.get(k) for k in ("order", "limit", "offset")):
		return tree
	return tree.this


def _strip_update_set_qualifiers(tree: exp.Expression) -> None:
	"""Drop the table-qualifier from `UPDATE ... SET` column targets; SQLite rejects
	``SET "tbl"."col" = val``, unlike MariaDB."""
	if not isinstance(tree, exp.Update):
		return
	for assignment in tree.args.get("expressions", []):
		target = assignment.this if isinstance(assignment, exp.EQ) else None
		if isinstance(target, exp.Column):
			target.set("table", None)


def _is_now_like(node: exp.Expression) -> bool:
	return isinstance(node, exp.CurrentTimestamp) or (
		isinstance(node, exp.Anonymous) and str(node.this).upper() == "NOW"
	)


def _collapse_now_interval_arithmetic(tree: exp.Expression) -> None:
	"""Fold raw MariaDB ``NOW()``/``CURRENT_TIMESTAMP`` +/- ``INTERVAL 'n' UNIT`` into one
	``datetime('now', '±n units')`` call -- SQLite has no INTERVAL type. This handles hand-written
	MariaDB date arithmetic in raw ``frappe.db.sql`` (query-builder output uses pypika's own SQLite
	rendering and is folded there instead, see ``query_builder/builder.py``)."""
	for node in list(tree.find_all((exp.Sub, exp.Add))):
		base, other = node.this, node.expression
		if not _is_now_like(base) or not isinstance(other, exp.Interval):
			continue

		unit = str(other.args.get("unit")).lower()
		# Only fold the simple `INTERVAL <int> <single-unit>` forms SQLite can express as a
		# datetime() modifier. Compound units (HOUR_MINUTE) or unmapped ones (QUARTER) are left
		# for sqlglot to render as-is rather than crashing the whole rewrite.
		if unit not in _INTERVAL_UNITS:
			continue
		try:
			n = int(str(other.this.this))
		except ValueError:
			continue
		if unit in ("week", "weeks"):
			n *= 7
		sign = "-" if isinstance(node, exp.Sub) else "+"
		modifier = f"{sign}{n} {_INTERVAL_UNITS[unit]}"
		node.replace(exp.Datetime(this=exp.Literal.string("now"), expression=exp.Literal.string(modifier)))


def _add_collate_nocase_to_orderby(tree: exp.Expression) -> None:
	"""Inject COLLATE NOCASE onto plain-column ORDER BY terms (including in subqueries) so text
	sort matches MariaDB: SQLite's default BINARY collation sorts '_' after letters, unlike
	MariaDB's default collation. Function-call terms are left alone, matching MariaDB's own
	behaviour of not applying its collation to an expression's result."""
	for select in tree.find_all(exp.Select):
		order = select.args.get("order")
		if not order:
			continue
		# Map each output name to the column it projects. MariaDB/Postgres bind a bare ORDER BY
		# term to the matching output column; SQLite instead calls it ambiguous when the name
		# also lives in a joined table, so qualify it the same way before adding COLLATE.
		outputs = {}
		for e in select.expressions:
			col = e.this if isinstance(e, exp.Alias) else e
			if isinstance(col, exp.Column):
				outputs[e.alias_or_name.lower()] = col
		for ordered in order.expressions:
			target = ordered.this
			if not isinstance(target, exp.Column) or target.find(exp.Collate):
				continue
			if not target.table:
				out = outputs.get(target.name.lower())
				if out is not None and out.table:
					target = out.copy()
					ordered.set("this", target)
			ordered.set("this", exp.Collate(this=target.copy(), expression=exp.Var(this="NOCASE")))


def _inline_having_aliases(tree: exp.Expression) -> None:
	"""Inline aggregate SELECT aliases referenced bare in HAVING; SQLite resolves a bare name
	in HAVING to a table column, not the SELECT alias."""
	for select in tree.find_all(exp.Select):
		having = select.args.get("having")
		if not having:
			continue
		agg_map = {
			item.alias_or_name.lower(): item.this
			for item in select.expressions
			if isinstance(item, exp.Alias) and isinstance(item.this, exp.AggFunc)
		}
		if not agg_map:
			continue
		for col in list(having.find_all(exp.Column)):
			agg = None if col.table else agg_map.get(col.name.lower())
			if agg is not None:
				col.replace(agg.copy())


def modify_query(query: str) -> str:
	"""Rewrite a MariaDB-flavoured SQL query for SQLite compatibility. See the module comment
	above for the overall approach."""
	query = str(query)

	if not _is_dml(query):
		return query.replace("`", '"')

	try:
		tree = sqlglot.parse_one(_mask_placeholders(query), read=_FrappeMySQL)
	except sqlglot.errors.ParseError:
		# A construct sqlglot's MariaDB/MySQL grammar doesn't accept (rare); only the cheap
		# identifier-quoting rewrite still applies.
		return query.replace("`", '"')

	tree = _unwrap_top_level_subquery(tree)
	_strip_update_set_qualifiers(tree)
	_collapse_now_interval_arithmetic(tree)
	_inline_having_aliases(tree)
	_add_collate_nocase_to_orderby(tree)

	return tree.sql(dialect=_FrappeSQLite)


_POSITIONAL_PARAM = re.compile(r"%s")


def _expand_sequence(value, bind_scalar) -> str:
	"""Turn a bound value into placeholder text.

	Scalar -> one placeholder, list/tuple/set -> "(a, b)", empty -> "(NULL)" (matches nothing),
	nested -> a row value like "((1, 2), (3, 4))". bind_scalar records one scalar and returns its
	placeholder; SQLite can't bind a whole sequence to one placeholder, so we expand it here.
	"""
	if not isinstance(value, list | tuple | set):
		return bind_scalar(value)
	if not value:
		return "(NULL)"
	return "(" + ", ".join(_expand_sequence(v, bind_scalar) for v in value) + ")"


def _bind_named_params(query: str, values: dict):
	"""Rewrite %(name)s placeholders to SQLite :name, expanding sequences (see _expand_sequence).

	Placeholders inside string literals (e.g. '%(x)s') are left alone. The caller's dict is not mutated.
	"""
	bind: dict = {}

	def replace(match):
		key = match.group(1)
		if key not in values:
			return match.group(0)

		def bind_scalar(value):
			# len(bind) keeps every generated name unique.
			name = f"{key}_{len(bind)}"
			bind[name] = value
			return f":{name}"

		return _expand_sequence(values[key], bind_scalar)

	rewritten = "".join(
		chunk if is_literal else _PARAM_COMP.sub(replace, chunk)
		for is_literal, chunk in _split_sql_literals(query)
	)
	return rewritten, bind


def _expand_positional_params(query: str, values):
	"""Rewrite %s placeholders to SQLite ?, expanding sequences so "WHERE name IN %s" works.

	Placeholders inside string literals (e.g. LIKE '%system%') are left alone.
	"""

	flat: list = []
	values_iter = iter(())  # the real iterator is set once values are normalised, below

	def substitute_only(q):
		# Plain %s -> ? outside string literals, no sequence expansion. Used as the fallback.
		return "".join(
			chunk if is_literal else chunk.replace("%s", "?") for is_literal, chunk in _split_sql_literals(q)
		)

	def bind_scalar(value):
		flat.append(value)
		return "?"

	def replace(_match):
		# Each %s, left to right, takes the next value; a sequence expands to several ? binds.
		return _expand_sequence(next(values_iter), bind_scalar)

	if not values:
		return substitute_only(query), values

	if not isinstance(values, list | tuple):
		values = (values,)

	# We need exactly one value per placeholder. If the counts disagree (e.g. a stray %s left
	# by an earlier substitution), don't guess -- just do the plain substitution.
	placeholder_count = sum(
		chunk.count("%s") for is_literal, chunk in _split_sql_literals(query) if not is_literal
	)
	if placeholder_count != len(values):
		return substitute_only(query), values

	values_iter = iter(values)
	rewritten = "".join(
		chunk if is_literal else _POSITIONAL_PARAM.sub(replace, chunk)
		for is_literal, chunk in _split_sql_literals(query)
	)
	return rewritten, flat
