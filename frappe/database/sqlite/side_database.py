# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Secondary SQLite database used as storage for `use_sqlite` DocTypes.

The site's primary database (MariaDB/Postgres) stays the default for every DocType.
DocTypes with `use_sqlite` enabled keep their rows in a single side file instead,
`<site>/db/doctype_store.db`, served by this class.

Everything here is an override of :class:`frappe.database.sqlite.database.SQLiteDatabase`;
connection handling, the type map, DDL, error taxonomy, query rewriting and transaction
control are inherited unchanged.
"""

import re
from pathlib import Path

import frappe
from frappe import _
from frappe.database.sqlite.database import SQLiteDatabase
from frappe.database.sqlite.router import use_primary_db
from frappe.database.sqlite.schema import SQLiteTable

#: Filename of the shared side database, relative to `<site>/db/`.
SQLITE_STORE_FILENAME = "doctype_store.db"

#: Label used as `cur_db_name`. Only ever surfaces in logs -- `get_db_path` ignores it.
SQLITE_STORE_NAME = "doctype_store"

# Double-quoted identifier: letters/digits/underscore, plus the spaces and hyphens that
# appear in `tabSales Invoice`-style table names. Deliberately narrower than "any quoted
# run", so a quoted string value isn't mistaken for a column name.
_QUOTED_IDENTIFIER_PATTERN = re.compile(r"\"([A-Za-z_][\w \-]*)\"")


class CrossDatabaseJoinError(frappe.ValidationError):
	"""Raised when one statement mixes SQLite-backed and primary-backed tables.

	The two stores are separate database engines, so no join across them is possible.
	Failing loudly here beats returning a silently wrong result set.
	"""


class SQLiteSideDatabase(SQLiteDatabase):
	def __init__(self):
		super().__init__(cur_db_name=SQLITE_STORE_NAME)
		# Statement routing is suspended while syncing schema: every statement a sync emits
		# targets this store, including the temp-table copies `SQLiteTable.alter` uses, whose
		# scratch names (`tabX_new`) are not real DocType tables.
		self._in_schema_sync = False

	def get_db_path(self):
		"""Return the shared side-store path.

		The base class derives the path from `cur_db_name`, which on a SQLite *site*
		points at the primary database. The side store is a fixed, separate file.
		"""
		return Path(frappe.get_site_path()) / "db" / SQLITE_STORE_FILENAME

	def connect(self):
		db_folder = self.get_db_path().parent
		if not db_folder.exists():
			db_folder.mkdir(parents=True, exist_ok=True)

		super().connect()

		# `autoname: autoincrement` doctypes fetch a value before insert via
		# frappe.database.sequence, which expects this bookkeeping table to exist.
		self.create_sequence_table()

	# ---------------------------------------------------------------- caching

	# The base class caches under the site-global keys `db_tables` and
	# `table_columns::<table>`, which the primary database also uses. Namespace both
	# so the two table listings can't overwrite each other.

	def get_tables(self, cached=True):
		"""Return list of tables in the side store."""
		to_query = not cached

		if cached:
			tables = frappe.cache.get_value("sqlite_store_db_tables")
			to_query = not tables

		if to_query:
			tables = self.sql("SELECT name FROM sqlite_master WHERE type='table';", pluck=True)
			frappe.cache.set_value("sqlite_store_db_tables", tables)

		return tables

	def get_db_table_columns(self, table) -> list[str]:
		"""Return list of column names from given table in the side store.

		Introspection is delegated as a whole call rather than as a statement: `PRAGMA` has no
		meaning on MariaDB or Postgres, so a foreign table has to be described by the primary
		database using its own syntax.
		"""
		if not self._owns(table):
			with use_primary_db() as primary:
				return primary.get_db_table_columns(table)

		key = f"sqlite_store_table_columns::{table}"
		columns = frappe.client_cache.get_value(key)
		if columns is None:
			columns = self.sql(f"PRAGMA table_info(`{table}`)", as_dict=True)
			columns = [col["name"] for col in columns]

			if columns:
				frappe.cache.set_value(key, columns)

		return columns

	def get_table_columns_description(self, table_name):
		"""Return list of columns with descriptions, from whichever store owns the table."""
		if not self._owns(table_name):
			with use_primary_db() as primary:
				return primary.get_table_columns_description(table_name)

		return super().get_table_columns_description(table_name)

	def table_exists(self, doctype, cached=True):
		"""Return True if the table exists in whichever store owns it."""
		if not self._owns(f"tab{doctype}"):
			with use_primary_db() as primary:
				return primary.table_exists(doctype, cached=cached)

		return super().table_exists(doctype, cached=cached)

	def _owns(self, table: str) -> bool:
		"""Return True if `table` belongs to this store.

		Non-`tab` tables (`__Auth`, sequence bookkeeping, sqlite_master) are ours by
		definition -- the side store keeps its own copies of the framework's side tables.
		"""
		from frappe.database.sqlite.router import get_sqlite_tables

		return not table.startswith("tab") or table in get_sqlite_tables()

	def clear_table_cache(self, table: str | None = None):
		"""Drop cached table/column listings after DDL."""
		frappe.cache.delete_value("sqlite_store_db_tables")
		if table:
			frappe.client_cache.delete_value(f"sqlite_store_table_columns::{table}")

	# ---------------------------------------------------------------- schema

	def updatedb(self, doctype, meta=None):
		"""Sync a DocType to its table in the side store.

		Overridden because the base implementation reads `issingle` from `tabDocType`,
		which lives in the primary database and has no counterpart here. Singles are
		excluded from SQLite-backed storage, so there is nothing to branch on.
		"""
		meta = meta or frappe.get_meta(doctype)

		# Drop the cached listings first: `DBTable.is_new` decides between CREATE and ALTER by
		# asking `get_tables()`, and a cached listing that no longer matches the file on disk
		# would send a brand-new table down the ALTER path.
		self.clear_table_cache(f"tab{doctype}")

		db_table = SQLiteTable(doctype, meta)
		self._in_schema_sync = True
		try:
			db_table.validate()
			db_table.sync()
		finally:
			self._in_schema_sync = False

		self.commit()
		self.clear_table_cache(f"tab{doctype}")

	# ---------------------------------------------------------------- routing

	def sql(self, *args, **kwargs):
		"""Execute on the side store, or hand the statement back to the primary database.

		A DocType save touches more than its own table -- `tabVersion`, `tabDocShare`,
		`__Auth` and friends all live in the primary database. Rather than requiring
		every caller to know which store it is addressing, statements are attributed by
		the tables they name:

		* references at least one SQLite-backed table -> run here
		* references only primary-backed tables -> delegate to the primary database
		* references both -> :class:`CrossDatabaseJoinError`

		Statements naming no `tab` table at all (PRAGMA, sqlite_master, sequence
		bookkeeping, transaction control) are internal to this store and run here.
		"""
		query = args[0] if args else kwargs.get("query")
		# Set by the router while a swap is active. Deliberately *not* `local.primary_db`,
		# which belongs to the read-replica machinery in frappe.connect_replica.
		primary = getattr(frappe.local, "sqlite_primary_db", None)

		if primary is not None and primary is not self and not self._in_schema_sync and not self._is_ddl(query):
			owned, foreign = self._classify_tables(query)

			if owned and foreign:
				raise CrossDatabaseJoinError(
					_(
						"Cannot query SQLite-backed table(s) {0} together with {1}: "
						"they are stored in separate databases."
					).format(", ".join(sorted(owned)), ", ".join(sorted(foreign)))
				)

			if foreign and not owned:
				query = self._adapt_for_primary(query, primary)
				if args:
					args = (query, *args[1:])
				else:
					kwargs["query"] = query
				return primary.sql(*args, **kwargs)

		return super().sql(*args, **kwargs)

	@staticmethod
	def _is_ddl(query) -> bool:
		"""Return True for schema statements, which are never routed elsewhere.

		DDL reaches this store only through `updatedb`, which runs for an owned DocType, so
		the target is known without inspecting the statement. Skipping attribution also avoids
		reading incidental identifiers as tables: `CREATE INDEX \\`tabApp Audit Log_creation_idx\\``
		names an index, not a second table.
		"""
		from frappe.database.database import DDL_QUERY_TYPES
		from frappe.database.utils import get_query_type

		try:
			return get_query_type(str(query)) in DDL_QUERY_TYPES
		except (TypeError, IndexError):
			return False

	@staticmethod
	def _adapt_for_primary(query, primary):
		"""Re-render SQLite identifier quoting for the primary backend.

		A statement built while the swap was active carries the SQLite dialect, which quotes
		identifiers with `"` (pypika's SQLLiteQueryBuilder.QUOTE_CHAR). MariaDB reads those as
		string literals, so they have to become backticks before the primary sees them. This is
		the inverse of the rewrite `frappe.database.sqlite.database.modify_query` already applies
		in the other direction.

		Only identifier-shaped tokens are rewritten, so a quoted string value is left alone.
		Postgres quotes identifiers the same way SQLite does and needs no adaptation.
		"""
		if primary.db_type != "mariadb":
			return query

		return _QUOTED_IDENTIFIER_PATTERN.sub(r"`\1`", str(query))

	def _classify_tables(self, query) -> tuple[set[str], set[str]]:
		"""Split the `tab` tables named in `query` into SQLite-backed and primary-backed.

		Uses the same patterns `Database._log_touched_tables` relies on. They require the
		segment after `tab` to start with a capital, which is what keeps ordinary words from
		being read as table names -- `type='table'` would otherwise scan as `tab` + `le`.
		A statement naming no table at all (PRAGMA, sqlite_master, sequence bookkeeping,
		transaction control) belongs to this store and yields two empty sets.
		"""
		if not query:
			return set(), set()

		from frappe.database.database import MULTI_WORD_PATTERN, SINGLE_WORD_PATTERN
		from frappe.database.sqlite.router import get_sqlite_tables

		sqlite_tables = get_sqlite_tables()
		query = str(query)
		tables = set()

		# Multi-word names first, blanking each match: `tabApp Audit Log` also matches the
		# single-word pattern as `tabApp`, which would look like a second, different table.
		def _collect_multi_word(match):
			tables.add(match.group(2))
			return " "

		remainder = MULTI_WORD_PATTERN.sub(_collect_multi_word, query)
		tables.update(groups[1] for groups in SINGLE_WORD_PATTERN.findall(remainder))

		owned = {table for table in tables if table in sqlite_tables}
		return owned, tables - owned
