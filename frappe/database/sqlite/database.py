import re
import sqlite3
import warnings
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlglot
from pypika.queries import QueryBuilder
from sqlglot import expressions as exp
from sqlglot.errors import ErrorLevel, SqlglotError

import frappe
from frappe.database.database import (
	TRANSACTION_DISABLED_MSG,
	Database,
)
from frappe.database.sqlite.compatibility import (
	combine_date_with_time_duration,
	convert_datetime_to_unix_timestamp,
	convert_sqlite_date,
	convert_sqlite_time,
	format_datetime_with_mariadb_tokens,
	json_contains_mariadb_value,
)
from frappe.database.sqlite.query_parameters import (
	convert_frappe_query_parameters,
	mask_query_parameters,
	render_query_with_bound_values,
	restore_transpiled_query_parameters,
)
from frappe.database.sqlite.schema import SQLiteTable
from frappe.database.utils import convert_backtick_identifiers
from frappe.utils import get_table_name, now

_TRANSPILABLE_STATEMENTS = (exp.Select, exp.Insert, exp.Update, exp.Delete, exp.Union)


class SequenceGeneratorLimitExceeded(sqlite3.Error):
	"""Raised when an emulated sequence with a max_value (and no cycle) is exhausted.

	SQLite has no native sequences (frappe emulates them, see
	``frappe.database.sequence``), so unlike MariaDB/Postgres there is no driver
	exception to reuse for this case.
	"""


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
	SequenceGeneratorLimitExceeded = SequenceGeneratorLimitExceeded

	def get_connection(self, read_only: bool = False):
		if not hasattr(self, "_session_time_zone"):
			self._session_time_zone = ZoneInfo("UTC")
		conn = self.create_connection(read_only)
		conn.create_function("regexp", 2, regexp)
		conn.create_function("regexp_replace", 3, regexp_replace)
		conn.create_function("regexp_like", 2, regexp_like)
		conn.create_function(
			"frappe_combine_datetime", 2, combine_date_with_time_duration, deterministic=True
		)
		conn.create_function("frappe_date_format", 2, format_datetime_with_mariadb_tokens, deterministic=True)
		conn.create_function("frappe_json_contains", 2, json_contains_mariadb_value, deterministic=True)
		conn.create_function("frappe_unix_timestamp", 1, self._convert_to_unix_timestamp)
		conn.create_function("now", 0, now)
		pragmas = {
			"journal_mode": "WAL",
			"synchronous": "NORMAL",
			"busy_timeout": 5000,  # in milliseconds
		}
		cursor = conn.cursor()
		for pragma, value in pragmas.items():
			cursor.execute(f"PRAGMA {pragma}={value}")
		cursor.close()
		return conn

	def create_connection(self, read_only: bool = False):
		db_path = self.get_db_path()
		sqlite3.register_converter("timestamp", lambda x: datetime.fromisoformat(x.decode()))
		sqlite3.register_converter("date", convert_sqlite_date)
		sqlite3.register_converter("time", convert_sqlite_time)
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

	def set_session_time_zone(self, timezone: str):
		self._session_time_zone = ZoneInfo(timezone)

	def _convert_to_unix_timestamp(self, value):
		return convert_datetime_to_unix_timestamp(value, self._session_time_zone)

	def setup_type_map(self):
		self.db_type = "sqlite"
		self.type_map = {
			"Currency": ("real", None),
			"Int": ("int", None),
			"Long Int": ("bigint", None),
			"Float": ("real", None),
			"Percent": ("real", None),
			"Check": ("integer", None),
			"Small Text": ("text", None),
			"Long Text": ("text", None),
			"Code": ("text", None),
			"Text Editor": ("text", None),
			"Markdown Editor": ("text", None),
			"HTML Editor": ("text", None),
			"Date": ("date", None),
			"Datetime": ("timestamp", None),
			"Time": ("time", None),
			"Text": ("text", None),
			"Data": ("varchar", self.VARCHAR_LEN),
			"Link": ("varchar", self.VARCHAR_LEN),
			"Dynamic Link": ("varchar", self.VARCHAR_LEN),
			"Password": ("text", None),
			"Select": ("varchar", self.VARCHAR_LEN),
			"Rating": ("real", None),
			"Read Only": ("varchar", self.VARCHAR_LEN),
			"Attach": ("text", None),
			"Attach Image": ("text", None),
			"Signature": ("text", None),
			"Color": ("varchar", self.VARCHAR_LEN),
			"Barcode": ("text", None),
			"Geolocation": ("text", None),
			"Duration": ("real", None),
			"Icon": ("varchar", self.VARCHAR_LEN),
			"Phone": ("varchar", self.VARCHAR_LEN),
			"Autocomplete": ("varchar", self.VARCHAR_LEN),
			"JSON": ("text", None),
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
		"""Change a column type while preserving the rest of the SQLite schema."""
		table_name = get_table_name(doctype)
		column_definitions = []
		column_names = []
		column_exists = False
		for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1):
			column_names.append(col["name"])
			if col["name"] == column:
				column_exists = True
				null_str = "" if nullable else " NOT NULL"
				default_str = "" if col["dflt_value"] is None else f" DEFAULT {col['dflt_value']}"
				column_definitions.append(f"`{col['name']}` {type}{null_str}{default_str}")
			else:
				column_definitions.append(get_column_definition(col))

		if not column_exists:
			raise frappe.InvalidColumnName(f"Column {column} does not exist in table {table_name}")

		rebuild_table(table_name, column_definitions, column_names)

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		"""Rename a column with SQLite's native schema-preserving operation."""
		table_name = get_table_name(doctype)
		column_names = [
			column["name"] for column in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=True)
		]
		if old_column_name not in column_names:
			raise frappe.InvalidColumnName(f"Column {old_column_name} does not exist in table {table_name}")
		self.sql_ddl(f"ALTER TABLE `{table_name}` RENAME COLUMN `{old_column_name}` TO `{new_column_name}`")

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
		columns = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		unique_columns, indexed_columns = set(), set()
		for index in get_table_indexes(table_name):
			if index["origin"] == "pk" or index["partial"]:
				continue
			if index["unique"] and len(index["columns"]) == 1:
				unique_columns.add(index["columns"][0])
			elif not index["unique"] and index["columns"]:
				indexed_columns.add(index["columns"][0])

		for column in columns:
			column["type"] = column["type"].lower()
			column["default"] = column["dflt_value"]
			column["not_nullable"] = bool(column["notnull"])
			column["unique"] = column["name"] in unique_columns
			column["index"] = column["name"] in indexed_columns
		return columns

	def get_column_type(self, doctype, column):
		"""Return column type from database."""
		table_name = get_table_name(doctype)
		result = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		for row in result:
			if row["name"] == column:
				return row["type"].lower()
		return None

	def has_index(self, table_name, index_name):
		return self.sql(f"SELECT * FROM pragma_index_list(`{table_name}`) WHERE name = %s", (index_name,))

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False) -> frappe._dict | None:
		"""Check if column exists for a specific fields in specified order."""
		indexes = self.sql(f"PRAGMA index_list(`{table_name}`)", as_dict=True)
		for index in indexes:
			if bool(index["unique"]) != unique or index["partial"]:
				continue
			index_info = self.sql(f"PRAGMA index_info(`{index['name']}`)", as_dict=True)
			if index_info and index_info[0]["name"] == fieldname and (not unique or len(index_info) == 1):
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
		original_fields = fields
		# SQLite indexes the complete value; a MariaDB prefix length is neither needed nor valid here.
		fields = [re.sub(r"\(\d+\)$", "", field) for field in fields]
		for field in fields:
			if not re.fullmatch(r"\w+", field):
				frappe.throw(f"Invalid index column: {field}")

		table_name = get_table_name(doctype)
		index_name = index_name or f"{table_name}_{self.get_index_name(fields)}"
		self.commit()
		columns = ", ".join(f"`{field}`" for field in fields)
		self.sql(f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}` ({columns})")

		# Ensure that DB migration doesn't clear this index, assuming this is manually added
		# via code or console.
		if (
			len(fields) == 1
			and original_fields == fields
			and not (frappe.flags.in_install or frappe.flags.in_migrate)
		):
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
		for field in fields:
			if not re.fullmatch(r"\w+", field):
				frappe.throw(f"Invalid unique column: {field}")
		table_name = get_table_name(doctype)
		if not constraint_name:
			constraint_name = f"{table_name}_unique_{'_'.join(fields)}"

		columns = ", ".join(f"`{field}`" for field in fields)
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
		return self._cursor.execute(query, values)

	def _transform_query(self, query, values):
		return convert_frappe_query_parameters(query, values)

	def mogrify(self, query, values):
		return render_query_with_bound_values(query, values)

	def log_query(self, query, query_type, values, debug):
		# sqlite3 cursors expose no equivalent of the executed statement, so the
		# mogrified query is what `last_query` reports. MariaDB and Postgres both
		# publish this attribute; without it anything reading `db.last_query`
		# (e.g. IntegrationTestCase.assertQueryCount) breaks only on SQLite.
		mogrified_query = self.lazy_mogrify(query, values)
		self.last_query = mogrified_query
		self._log_query(mogrified_query, query_type, debug, query)
		return mogrified_query

	def sql(self, *args, **kwargs):
		query = args[0] if args else kwargs.get("query")
		skip_transpilation = kwargs.pop("_skip_sqlite_transpilation", False) or isinstance(
			query, QueryBuilder
		)
		if args and not skip_transpilation:
			# since tuple is immutable
			args = list(args)
			args[0], positional_parameter_order = _modify_query(args[0])
			if len(args) > 1:
				args[1] = _reorder_positional_parameters(args[1], positional_parameter_order)
			elif "values" in kwargs:
				kwargs["values"] = _reorder_positional_parameters(
					kwargs["values"], positional_parameter_order
				)
			args = tuple(args)
		elif kwargs.get("query") and not skip_transpilation:
			kwargs["query"], positional_parameter_order = _modify_query(kwargs["query"])
			if "values" in kwargs:
				kwargs["values"] = _reorder_positional_parameters(
					kwargs["values"], positional_parameter_order
				)

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
		# Unlike MariaDB, SQLite DDL participates in the current transaction. Either the complete replacement and all indexes/triggers succeed, or the original table remains untouched.
		pass


def modify_query(query):
	"""Translate raw MariaDB-style SQL into SQLite SQL."""
	return _modify_query(query)[0]


def _modify_query(query) -> tuple[str, tuple[int, ...]]:
	query = str(query)
	transpiled = _transpile_to_sqlite(query)
	return transpiled if transpiled is not None else (_legacy_modify_query(query), ())


@lru_cache(maxsize=1024)
def _transpile_to_sqlite(query: str) -> tuple[str, tuple[int, ...]] | None:
	"""Returns the query rewritten for SQLite, or None if sqlglot couldn't
	parse it (as MariaDB SQL), or didn't parse it as one of _TRANSPILABLE_STATEMENTS.

	`%s` / `%(name)s` DB-API placeholders aren't valid MySQL expressions on their own. They are replaced only when they are SQL placeholder tokens, so identical text inside strings and comments remains the same.
	"""
	try:
		masked_query, parameters = mask_query_parameters(query)
		parsed_queries = sqlglot.parse(masked_query, read="mysql")
		if len(parsed_queries) != 1 or parsed_queries[0] is None:
			return None

		parsed = parsed_queries[0]
		if not isinstance(parsed, _TRANSPILABLE_STATEMENTS):
			return None

		# MariaDB permits COALESCE(x), but SQLite requires at least two arguments.
		parsed = parsed.transform(_unwrap_single_argument_coalesce)

		# SQLite has no row-level locks. Remove only this known incompatibility;
		# any other unsupported construct must take the safe fallback below.
		for select in parsed.find_all(exp.Select):
			select.set("locks", None)

		rewritten = parsed.sql(dialect="sqlite", unsupported_level=ErrorLevel.RAISE)
		return restore_transpiled_query_parameters(rewritten, parameters)
	except (SqlglotError, ValueError):
		return None


def _unwrap_single_argument_coalesce(node):
	while isinstance(node, exp.Coalesce) and not node.expressions:
		node = node.this.copy()
	return node


def _reorder_positional_parameters(values, positional_parameter_order: tuple[int, ...]):
	if (
		not isinstance(values, list | tuple)
		or not positional_parameter_order
		or positional_parameter_order == tuple(range(len(positional_parameter_order)))
	):
		return values

	reordered = (values[index] for index in positional_parameter_order)
	return list(reordered) if isinstance(values, list) else tuple(reordered)


def _legacy_modify_query(query: str) -> str:
	"""Fallback for queries sqlglot can't parse"""
	# Replace backticks only when they delimit identifiers. Literal backticks in
	# strings and comments must survive the fallback translation unchanged.
	query = convert_backtick_identifiers(query)
	query = replace_locate_with_instr(query)

	if re.search("from tab", query, flags=re.IGNORECASE):
		query = re.sub("from tab([a-zA-Z]*)", r'from "tab\1"', query, flags=re.IGNORECASE)

	return query


def get_column_definition(column: dict) -> str:
	"""Rebuild a column definition from SQLite's PRAGMA table_info output."""
	definition = f"`{column['name']}` {column['type']}"
	if column["notnull"]:
		definition += " NOT NULL"
	if column["dflt_value"] is not None:
		definition += f" DEFAULT {column['dflt_value']}"
	return definition


def get_table_indexes(table_name: str) -> list[dict]:
	"""Snapshot all indexes needed to reproduce a table's constraints."""
	indexes = []
	for index in frappe.db.sql(f"PRAGMA index_list(`{table_name}`)", as_dict=True):
		columns = tuple(
			column["name"]
			for column in frappe.db.sql(f"PRAGMA index_info(`{index['name']}`)", as_dict=True)
			if column["name"] is not None
		)
		definition = frappe.db.sql(
			"SELECT sql FROM sqlite_master WHERE type = 'index' AND name = %s",
			(index["name"],),
			pluck=True,
		)
		indexes.append(
			{
				"name": index["name"],
				"unique": bool(index["unique"]),
				"origin": index["origin"],
				"partial": bool(index["partial"]),
				"columns": columns,
				"sql": definition[0] if definition else None,
			}
		)
	return indexes


def _table_uses_autoincrement(table_name: str) -> bool:
	table_sql = frappe.db.sql(
		"SELECT sql FROM sqlite_master WHERE type = 'table' AND name = %s", (table_name,), pluck=True
	)
	return bool(table_sql and table_sql[0] and re.search(r"\bAUTOINCREMENT\b", table_sql[0], re.I))


def _get_autoincrement_sequence(table_name: str) -> int | None:
	if not _table_uses_autoincrement(table_name):
		return None
	sequence = frappe.db.sql("SELECT seq FROM sqlite_sequence WHERE name = %s", (table_name,), pluck=True)
	return sequence[0] if sequence else None


def _restore_autoincrement_sequence(table_name: str, sequence: int | None) -> None:
	if sequence is None or not _table_uses_autoincrement(table_name):
		return
	current_sequence = frappe.db.sql(
		"SELECT seq FROM sqlite_sequence WHERE name = %s", (table_name,), pluck=True
	)
	sequence = max(sequence, current_sequence[0] if current_sequence else 0)
	frappe.db.sql("DELETE FROM sqlite_sequence WHERE name = %s", (table_name,))
	frappe.db.sql("INSERT INTO sqlite_sequence (name, seq) VALUES (%s, %s)", (table_name, sequence))


def _append_primary_key(column_definitions: list[str], table_name: str) -> None:
	primary_key = sorted(
		(column["pk"], column["name"])
		for column in frappe.db.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=True)
		if column["pk"]
	)
	if not primary_key:
		return

	if len(primary_key) == 1 and _table_uses_autoincrement(table_name):
		primary_key_name = primary_key[0][1]
		prefix = f"`{primary_key_name}` "
		for index, definition in enumerate(column_definitions):
			definition_parts = definition[len(prefix) :].split() if definition.startswith(prefix) else []
			if definition_parts and definition_parts[0].upper() == "INTEGER":
				column_definitions[index] += " PRIMARY KEY AUTOINCREMENT"
				return

	quoted_columns = ", ".join(f"`{name}`" for _, name in primary_key)
	column_definitions.append(f"PRIMARY KEY ({quoted_columns})")


def _should_drop_index(index: dict, drop_index_fields: set[str], drop_unique_fields: set[str]) -> bool:
	if index["partial"] or len(index["columns"]) != 1:
		return False
	fieldname = index["columns"][0]
	if index["unique"]:
		return fieldname in drop_unique_fields
	return fieldname in drop_index_fields


def _append_unique_constraints(
	column_definitions: list[str],
	indexes: list[dict],
	drop_unique_fields: set[str],
) -> set[tuple[bool, tuple[str, ...]]]:
	preserved = set()
	for index in indexes:
		if index["origin"] != "u" or _should_drop_index(index, set(), drop_unique_fields):
			continue
		if not index["columns"]:
			raise RuntimeError(f"Cannot preserve SQLite unique constraint {index['name']}")
		quoted_columns = ", ".join(f"`{column}`" for column in index["columns"])
		column_definitions.append(f"UNIQUE ({quoted_columns})")
		preserved.add((True, index["columns"]))
	return preserved


def _restore_explicit_indexes(
	indexes: list[dict],
	*,
	drop_index_fields: set[str],
	drop_unique_fields: set[str],
	preserved: set[tuple[bool, tuple[str, ...]]],
) -> set[tuple[bool, tuple[str, ...]]]:
	for index in indexes:
		if index["origin"] == "pk" or index["sql"] is None:
			continue
		if _should_drop_index(index, drop_index_fields, drop_unique_fields):
			continue
		index_sql = re.sub(r"\s*/\*\s*FRAPPE_TRACE_ID:.*?\*/\s*$", "", index["sql"], flags=re.S)
		frappe.db.sql(index_sql)
		preserved.add((index["unique"], index["columns"]))
	return preserved


def _get_table_triggers(table_name: str) -> list[str]:
	return frappe.db.sql(
		"SELECT sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = %s AND sql IS NOT NULL",
		(table_name,),
		pluck=True,
	)


def rebuild_table(
	table_name: str,
	column_definitions: list[str],
	column_names: list[str],
	*,
	drop_index_fields: set[str] | None = None,
	drop_unique_fields: set[str] | None = None,
	pre_rebuild_queries: list[str] | None = None,
	post_rebuild_queries: list[str] | None = None,
) -> set[tuple[bool, tuple[str, ...]]]:
	"""Rebuild a SQLite table without discarding its schema-owned behavior."""
	drop_index_fields = drop_index_fields or set()
	drop_unique_fields = drop_unique_fields or set()
	pre_rebuild_queries = pre_rebuild_queries or []
	post_rebuild_queries = post_rebuild_queries or []
	indexes = get_table_indexes(table_name)
	triggers = _get_table_triggers(table_name)
	autoincrement_sequence = _get_autoincrement_sequence(table_name)

	_append_primary_key(column_definitions, table_name)
	preserved = _append_unique_constraints(column_definitions, indexes, drop_unique_fields)

	temp_table = f"{table_name}__rebuild_{frappe.generate_hash(length=10)}"
	quoted_columns = ", ".join(f"`{column}`" for column in column_names)

	# Keep the entire replacement in one transaction so a failed copy or index recreation cannot strand a partial schema or discard the original table.
	frappe.db.commit()
	try:
		for query in pre_rebuild_queries:
			frappe.db.sql(query)
		frappe.db.sql(f"CREATE TABLE `{temp_table}` (\n{','.join(column_definitions)}\n)")
		frappe.db.sql(
			f"INSERT INTO `{temp_table}` ({quoted_columns}) SELECT {quoted_columns} FROM `{table_name}`"
		)
		frappe.db.sql(f"DROP TABLE `{table_name}`")
		frappe.db.sql(f"ALTER TABLE `{temp_table}` RENAME TO `{table_name}`")

		preserved = _restore_explicit_indexes(
			indexes,
			drop_index_fields=drop_index_fields,
			drop_unique_fields=drop_unique_fields,
			preserved=preserved,
		)
		for trigger in triggers:
			frappe.db.sql(trigger)
		_restore_autoincrement_sequence(table_name, autoincrement_sequence)
		for query in post_rebuild_queries:
			frappe.db.sql(query)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise
	return preserved


def replace_locate_with_instr(query: str) -> str:
	# instr is the locate equivalent in SQLite
	if re.search(r"locate\(", query, flags=re.IGNORECASE):
		query = re.sub(r"locate\(([^,]+),([^)]+)\)", r"instr(\2, \1)", query, flags=re.IGNORECASE)
	return query


def regexp(expr: str | None, item: str | None) -> bool | None:
	"""
	Define regexp implementation for SQLite manually

	Although it works in the CLI - doesn't work through python
	"""
	if expr is None or item is None:
		return None
	return re.search(expr, item) is not None


def regexp_replace(item: str, pattern: str, repl: str) -> str:
	"""
	Define regexp_replace implementation for SQLite
	"""
	return re.sub(pattern, repl, item)


def regexp_like(item: str | None, expr: str | None) -> bool | None:
	return regexp(expr, item)
