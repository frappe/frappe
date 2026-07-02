import datetime
import re
from contextlib import contextmanager

import psycopg2
import psycopg2.extensions
from psycopg2 import sql
from psycopg2.errorcodes import (
	CLASS_INTEGRITY_CONSTRAINT_VIOLATION,
	DATATYPE_MISMATCH,
	DEADLOCK_DETECTED,
	DUPLICATE_COLUMN,
	INSUFFICIENT_PRIVILEGE,
	INVALID_TEXT_REPRESENTATION,
	NUMERIC_VALUE_OUT_OF_RANGE,
	SERIALIZATION_FAILURE,
	STRING_DATA_RIGHT_TRUNCATION,
	UNDEFINED_COLUMN,
	UNDEFINED_TABLE,
	UNIQUE_VIOLATION,
)
from psycopg2.errors import (
	InterfaceError,
	LockNotAvailable,
	ReadOnlySqlTransaction,
	SequenceGeneratorLimitExceeded,
	SyntaxError,
)
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED

import frappe
from frappe.database.database import CREATE_OR_DROP, Database
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


def _cast_time_as_timedelta(value, cursor):
	"""Return TIME columns as ``timedelta`` to match MariaDB.

	psycopg2 decodes a postgres ``time without time zone`` to ``datetime.time``, but frappe models
	Time fields as ``timedelta`` everywhere (that is what MariaDB's driver returns). Returning
	``datetime.time`` here makes the two backends diverge and breaks frappe's typed value handling.
	"""
	if value is None:
		return None
	hms, _, frac = value.partition(".")
	microseconds = int(frac.ljust(6, "0")[:6]) if frac else 0
	hours, minutes, seconds = (int(part) for part in hms.split(":"))
	return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)


# OID 1083 == `time without time zone` (the type frappe uses for Time fields)
TIME2TIMEDELTA = psycopg2.extensions.new_type((1083,), "TIME2TIMEDELTA", _cast_time_as_timedelta)
psycopg2.extensions.register_type(TIME2TIMEDELTA)

# OIDs 114 / 3802 == `json` / `jsonb`. psycopg2 auto-parses these into python dict/list, but frappe
# models JSON fields as *strings* (the value MariaDB's longtext returns) and json.loads them on
# demand. A parsed value diverges from MariaDB and breaks round-tripping -- e.g. re-saving a doc
# whose JSON field came back as a list fails get_valid_dict's "cannot be a list" check. Return the
# raw text instead so both backends behave identically.
JSON2STR = psycopg2.extensions.new_type((114, 3802), "JSON2STR", lambda value, cursor: value)
psycopg2.extensions.register_type(JSON2STR)

LOCATE_SUB_PATTERN = re.compile(r"locate\(([^,]+),([^)]+)(\)?)\)", flags=re.IGNORECASE)
LOCATE_QUERY_PATTERN = re.compile(r"locate\(", flags=re.IGNORECASE)
PG_TRANSFORM_PATTERN = re.compile(r"([=><]+)\s*([+-]?\d+)(\.0)?(?![a-zA-Z\.\d])")
FROM_TAB_PATTERN = re.compile(r"from tab([\w-]*)", flags=re.IGNORECASE)
# MySQL's REGEXP operator -> postgres `~*` (case-insensitive, matching MySQL's default collation)
REGEXP_PATTERN = re.compile(r"\sREGEXP\s", flags=re.IGNORECASE)

# Index methods accepted by add_index(using=...): the two custom GIN modes plus postgres'
# native access methods. Anything else is rejected before it reaches the DDL string.
INDEX_METHODS = frozenset({"gin_trgm", "gin_fulltext", "btree", "hash", "gist", "gin", "brin", "spgist"})


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
		# Treat serialization failures like deadlocks: both are retriable transaction-rollback
		# (class 40) errors. READ COMMITTED (the default now) doesn't raise SERIALIZATION_FAILURE
		# on plain write conflicts, but transactions explicitly run at a stricter level still can;
		# keep classifying it here so those route through frappe's deadlock retry instead of
		# surfacing as an unhandled query error.
		return getattr(e, "pgcode", None) in (DEADLOCK_DETECTED, SERIALIZATION_FAILURE)

	@staticmethod
	def is_timedout(e):
		# http://initd.org/psycopg/docs/extensions.html?highlight=datatype#psycopg2.extensions.QueryCanceledError
		return isinstance(e, (psycopg2.extensions.QueryCanceledError | LockNotAvailable))

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
		# Any unique-constraint violation that isn't the primary key (those are surfaced as
		# DuplicateEntryError first). This mirrors MariaDB, whose duplicate-entry error covers every
		# unique index regardless of name -- frappe's custom indexes (e.g. `unique_item_warehouse`)
		# don't carry the `_key` suffix postgres auto-generates, so a name match alone misses them.
		return PostgresExceptionUtil.is_duplicate_entry(
			e
		) and not PostgresExceptionUtil.is_primary_key_violation(e)

	@staticmethod
	def is_duplicate_fieldname(e):
		return getattr(e, "pgcode", None) == DUPLICATE_COLUMN

	@staticmethod
	def is_statement_timeout(e):
		return PostgresDatabase.is_timedout(e) or isinstance(e, frappe.QueryTimeoutError)

	@staticmethod
	def is_data_too_long(e):
		return getattr(e, "pgcode", None) == STRING_DATA_RIGHT_TRUNCATION

	@staticmethod
	def is_data_truncated(e):
		# a value cannot be cast to the column's new type -- e.g. changing a field holding
		# "not a number" to Int. MariaDB reports TRUNCATED_WRONG_VALUE; postgres is stricter and
		# aborts the ALTER: it refuses to auto-cast the column (datatype mismatch) or a value fails
		# the cast (invalid representation / numeric out of range).
		return getattr(e, "pgcode", None) in (
			DATATYPE_MISMATCH,
			INVALID_TEXT_REPRESENTATION,
			NUMERIC_VALUE_OUT_OF_RANGE,
		)

	@staticmethod
	def is_db_table_size_limit(e) -> bool:
		return False

	@staticmethod
	def is_interface_error(e):
		return isinstance(e, InterfaceError)


class PostgresDatabase(PostgresExceptionUtil, Database):
	REGEX_CHARACTER = "~"
	default_port = "5432"

	def setup_type_map(self):
		self.db_type = "postgres"
		self.type_map = {
			"Currency": ("decimal", "21,9"),
			"Int": ("int", None),
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

	@property
	def db_schema(self):
		return frappe.conf.get("db_schema", "public").replace("'", "").replace('"', "")

	def connect(self):
		super().connect()

		self._cursor.execute("SET search_path TO %s", (self.db_schema,))

	def get_connection(self):
		conn_settings = {
			"dbname": self.cur_db_name,
			"user": self.user,
			# libpg defaults to default socket if not specified
			"host": self.host or self.socket,
		}
		# libpq's GSSAPI (krb5) path is not fork-safe; with the default gssencmode=prefer RQ work
		# horses segfault on fork ("work-horse terminated unexpectedly"). The option exists from
		# libpq 12, so guard on the runtime version (an older client lib would reject it); validate
		# any site-config override against libpq's modes so a bad value can't break every connection.
		if psycopg2.extensions.libpq_version() >= 120000:
			gssencmode = str(frappe.conf.get("db_gssencmode") or "disable")
			if gssencmode not in ("disable", "allow", "prefer", "require"):
				gssencmode = "disable"
			conn_settings["gssencmode"] = gssencmode
		if self.password:
			conn_settings["password"] = self.password
		if not self.socket and self.port:
			conn_settings["port"] = self.port

		conn = psycopg2.connect(**conn_settings)
		conn.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)

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
		"""Return database size in MB"""
		db_size = self.sql(
			"SELECT (pg_database_size(%s) / 1024 / 1024) as database_size", self.cur_db_name, as_dict=True
		)
		return db_size[0].get("database_size")

	def _transform_result(self, result: list[tuple] | tuple[tuple]) -> tuple[tuple]:
		return tuple(result) if isinstance(result, list) else result

	# pylint: disable=W0221
	def sql(self, query, values=EmptyQueryValues, *args, **kwargs):
		return super().sql(modify_query(query), modify_values(values), *args, **kwargs)

	def lazy_mogrify(self, *args, **kwargs) -> str:
		return self.last_query

	def get_tables(self, cached=True):
		"""Return list of tables."""
		cache_key = f"db_tables::{self.db_schema}"
		to_query = not cached

		if cached:
			tables = frappe.client_cache.get_value(cache_key)
			to_query = not tables

		if to_query:
			tables = [
				d[0]
				for d in self.sql(
					"""select table_name
				from information_schema.tables
				where table_catalog=%s
					and table_type = 'BASE TABLE'
					and table_schema=%s""",
					(self.cur_db_name, self.db_schema),
				)
			]
			frappe.client_cache.set_value(cache_key, tables)

		return tables

	@staticmethod
	def clear_db_table_cache(query_type: str):
		if query_type in CREATE_OR_DROP:
			frappe.client_cache.delete_keys("db_tables::*")

	def get_db_table_columns(self, table) -> list[str]:
		"""Returns list of column names from given table."""
		key = f"table_columns::{table}"
		if (columns := frappe.client_cache.get_value(key)) is not None:
			return columns

		information_schema = frappe.qb.Schema("information_schema")

		columns = (
			frappe.qb.from_(information_schema.columns)
			.select(information_schema.columns.column_name)
			.where(
				(information_schema.columns.table_name == table)
				& (information_schema.columns.table_schema == self.db_schema)
			)
			.run(pluck=True)
		)

		frappe.client_cache.set_value(key, columns)

		return columns

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
			f"SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_NAME = '{table_name}' and table_schema='{frappe.conf.get('db_schema', 'public')}'"
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

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		table_name = get_table_name(doctype)
		frappe.db.sql_ddl(
			f"ALTER TABLE `{table_name}` RENAME COLUMN `{old_column_name}` TO `{new_column_name}`"
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
		if "__global_search" not in self.get_tables():
			self.sql(
				f"""create table "__global_search"(
				doctype varchar(100),
				name varchar({self.VARCHAR_LEN}),
				title varchar({self.VARCHAR_LEN}),
				content text,
				route varchar({self.VARCHAR_LEN}),
				published int not null default 0,
				unique (doctype, name))"""
			)
		# GIN index over the full-text vector so search()/web_search() do an index scan instead of
		# recomputing to_tsvector for every row. Runs unconditionally (CREATE INDEX IF NOT EXISTS is
		# idempotent) so an existing deployment that already has the table still gets it on upgrade.
		# Expression must match the query's to_tsvector('english', content).
		self.sql_ddl(
			"""CREATE INDEX IF NOT EXISTS "__global_search_fts"
			ON "__global_search" USING gin (to_tsvector('english', content))"""
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

			db_table.sync()
			self.commit()

	@staticmethod
	def get_on_duplicate_update(key="name"):
		if isinstance(key, list):
			key = '", "'.join(key)
		return f'ON CONFLICT ("{key}") DO UPDATE SET '

	def check_implicit_commit(self, query, query_type):
		pass  # postgres can run DDL in transactions without implicit commits

	def has_index(self, table_name, index_name):
		return self.sql(
			"""SELECT 1 FROM pg_indexes WHERE tablename=%s
			and schemaname = %s
			and indexname=%s limit 1""",
			(table_name, self.db_schema, index_name),
		)

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False) -> frappe._dict | None:
		"""Check if a column is the leading column of a single-column index.

		Cross-db counterpart of the MariaDB implementation (which uses ``SHOW INDEX`` with
		``Seq_in_index = 1`` and a single-column constraint). Uses the PostgreSQL system
		catalogs so callers stay db-agnostic.
		"""
		result = self.sql(
			f"""
			SELECT ic.relname AS "Key_name"
			FROM pg_index i
			JOIN pg_class tc ON tc.oid = i.indrelid
			JOIN pg_class ic ON ic.oid = i.indexrelid
			JOIN pg_namespace n ON n.oid = tc.relnamespace
			JOIN pg_attribute a ON a.attrelid = tc.oid AND a.attnum = i.indkey[0]
			WHERE tc.relname = %(table_name)s
				AND n.nspname = %(schema)s
				AND a.attname = %(fieldname)s
				AND i.indisunique = {"true" if unique else "false"}
				AND i.indnkeyatts = 1
			LIMIT 1
			""",
			{"table_name": table_name, "schema": self.db_schema, "fieldname": fieldname},
			as_dict=True,
		)
		return result[0] if result else None

	def add_index(
		self, doctype: str, fields: list, index_name: str | None = None, using=None, where=None, include=None
	):
		"""Creates an index with given fields if not already created.

		Default index name is `<table>_<field1>_<field2>_index` (table-qualified so it is unique
		per *schema*, as postgres requires).

		using: index kind beyond the default btree --
			"gin_trgm"     GIN + gin_trgm_ops for fast LIKE/ILIKE substring search (needs pg_trgm)
			"gin_fulltext" GIN over to_tsvector(...) for full-text search on text columns
			or a bare access method ("btree", "hash", "gist", "gin", "brin", "spgist").
		where: predicate for a partial index, e.g. "docstatus < 2". A trusted DDL fragment
			interpolated verbatim -- callers MUST NOT pass user-supplied input.
		include: non-key columns to carry in a covering (INCLUDE) btree index, so an index-only
			scan answers the query without touching the heap.
		"""
		from frappe.database.postgres.schema import get_qualified_index_name

		# `using` is interpolated into DDL, so reject anything outside the known-safe set.
		if using and using not in INDEX_METHODS:
			frappe.throw(f"Unsupported index method: {using}")

		table_name = get_table_name(doctype)
		clean_fields = [re.sub(r"\(.*\)", "", field) for field in fields]
		# Column identifiers are interpolated into the DDL string, so reject anything that isn't a
		# plain name -- a value like `id") ...; DROP TABLE ...` would otherwise inject into it.
		for column in (*clean_fields, *(include or ())):
			if not re.fullmatch(r"\w+", column):
				frappe.throw(f"Invalid index column: {column}")
		# postgres index names are per-schema, not per-table: an unqualified default name collides
		# across tables sharing these fields and `CREATE INDEX IF NOT EXISTS` then silently skips
		# all but the first, leaving the index missing. Qualify with the table (and `using`, so a
		# trigram index never clashes with the plain one on the same column).
		index_name = index_name or get_qualified_index_name(table_name, clean_fields, using)

		if using == "gin_trgm":
			self.sql_ddl("CREATE EXTENSION IF NOT EXISTS pg_trgm")

		method = f" USING {'gin' if using in ('gin_trgm', 'gin_fulltext') else using}" if using else ""
		include_clause = f""" INCLUDE ("{'", "'.join(include)}")""" if include else ""
		condition = f" WHERE {where}" if where else ""
		self.sql_ddl(
			f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{self.db_schema}"."{table_name}"'
			f"{method} ({self._index_target(clean_fields, using)}){include_clause}{condition}"
		)

	def _index_target(self, fields: list[str], using: str | None) -> str:
		"""The column list (or functional expression) an index is built over, per `using` mode."""
		if using == "gin_trgm":
			return ", ".join(f'"{field}" gin_trgm_ops' for field in fields)
		if using == "gin_fulltext":
			# 'english' regconfig keeps to_tsvector immutable so it can be indexed; the search query
			# must use the same config. ponytail: hardcoded -- add a `config` arg if multilingual
			# full-text is ever needed.
			document = (
				f'"{fields[0]}"'
				if len(fields) == 1
				else " || ' ' || ".join(f"coalesce(\"{field}\", '')" for field in fields)
			)
			return f"to_tsvector('english', {document})"
		return '"' + '", "'.join(fields) + '"'

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
			AND constraint_schema=%s
			AND CONSTRAINT_NAME=%s""",
			("tab" + doctype, self.db_schema, constraint_name),
		):
			self.commit()

			self.sql(
				sql.SQL(
					"""ALTER TABLE {schema}.{table}
					ADD CONSTRAINT {constraint} UNIQUE ({fields})"""
				)
				.format(
					schema=sql.Identifier(self.db_schema),
					table=sql.Identifier("tab" + doctype),
					constraint=sql.Identifier(constraint_name),
					fields=sql.SQL(", ").join(sql.Identifier(field) for field in fields),
				)
				.as_string(self._conn)
			)

	def get_table_columns_description(self, table_name):
		"""Return list of columns with description."""
		# The `index`/`unique` flags say whether the column is the LEADING column of a
		# (non-unique / unique-non-primary) index -- mirroring MariaDB's `Seq_in_index = 1`
		# check. We resolve the leading column precisely from the catalogs (indkey[0]).
		# A substring match on indexdef would false-positive any column whose name appears
		# anywhere in a composite index's definition (e.g. `company` matching
		# `posting_date_company_index`), which then wrongly suppresses creating its own index.
		# pylint: disable=W1401
		return self.sql(
			f"""
			SELECT a.column_name AS name,
			CASE LOWER(a.data_type)
				WHEN 'character varying' THEN CONCAT('varchar(', a.character_maximum_length ,')')
				WHEN 'timestamp without time zone' THEN 'timestamp'
				WHEN 'integer' THEN 'int'
				WHEN 'numeric' THEN CONCAT('decimal(', a.numeric_precision, ',', a.numeric_scale, ')')
				ELSE a.data_type
			END AS type,
			COALESCE(BOOL_OR(NOT b.is_unique), false) AS index,
			SPLIT_PART(COALESCE(a.column_default, NULL), '::', 1) AS default,
			COALESCE(BOOL_OR(b.is_unique AND NOT b.is_primary), false) AS unique,
			COALESCE(a.is_nullable = 'NO', false) AS not_nullable
			FROM information_schema.columns a
			LEFT JOIN (
				SELECT att.attname AS column_name,
					i.indisunique AS is_unique,
					i.indisprimary AS is_primary
				FROM pg_index i
				JOIN pg_class tc ON tc.oid = i.indrelid
				JOIN pg_namespace n ON n.oid = tc.relnamespace
				JOIN pg_attribute att ON att.attrelid = tc.oid AND att.attnum = i.indkey[0]
				WHERE tc.relname = '{table_name}' AND n.nspname = '{self.db_schema}'
			) b ON b.column_name = a.column_name
			WHERE a.table_name = '{table_name}'
				AND a.table_schema = '{self.db_schema}'
			GROUP BY a.column_name, a.data_type, a.column_default, a.character_maximum_length, a.is_nullable, a.numeric_precision, a.numeric_scale;
		""",
			as_dict=1,
		)

	def get_column_type(self, doctype, column):
		"""Return column type from database."""
		information_schema = frappe.qb.Schema("information_schema")
		table = get_table_name(doctype)

		return (
			frappe.qb.from_(information_schema.columns)
			.select(information_schema.columns.data_type)
			.where(
				(information_schema.columns.table_name == table)
				& (information_schema.columns.column_name == column)
				& (information_schema.columns.table_schema == self.db_schema)
			)
			.run(pluck=True)[0]
		)

	def get_database_list(self):
		return self.sql("SELECT datname FROM pg_database", pluck=True)

	def _estimate_count(self, table: str) -> int:
		from frappe.utils.data import cint

		# Scope to current schema to avoid cross-site estimates
		count = self.sql(
			"select c.reltuples from pg_class c join pg_namespace n on n.oid = c.relnamespace where c.relname = %s and n.nspname = %s and c.relkind = 'r'",
			(table, self.db_schema),
		)
		return cint(count[0][0]) if count else 0

	@contextmanager
	def unbuffered_cursor(self):
		"""Unbuffered cursor in Postgres can only call .execute() once,
		usage:
			with frappe.db.unbuffered_cursor():
				frappe.db.sql()
		"""
		try:
			if not self._conn:
				self.connect()
			original_cursor = self._cursor
			new_cursor = self._cursor = self._conn.cursor(name="ss_cursor")
			yield
		finally:
			self._cursor = original_cursor
			new_cursor.close()

	@contextmanager
	def advisory_lock(self, key, *, timeout=10):
		"""Hold a session-level advisory lock for the duration of the `with` block. Session-scoped
		(pg_advisory_lock) so it survives any intermediate commits the caller makes -- a txn-scoped
		lock would release at the first commit. Polls pg_try_advisory_lock up to `timeout` seconds,
		then raises QueryTimeoutError. `key` is hashed to the bigint the lock functions expect."""
		import hashlib
		import time

		from frappe.exceptions import QueryTimeoutError

		lock_key = int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:8], "big", signed=True)
		deadline = time.monotonic() + timeout
		while not self.sql("SELECT pg_try_advisory_lock(%s)", (lock_key,))[0][0]:
			if time.monotonic() >= deadline:
				raise QueryTimeoutError(f"Could not acquire advisory lock {key!r} within {timeout}s")
			time.sleep(0.1)
		try:
			yield
		finally:
			try:
				self.sql("SELECT pg_advisory_unlock(%s)", (lock_key,))
			except Exception:
				# A DB error inside the block leaves the transaction aborted, so the unlock above
				# fails and the session-scoped lock would leak (ROLLBACK does not release it). Clear
				# the aborted state and release. Guarded so a failed cleanup never masks the original
				# error -- a dropped session releases the lock anyway.
				try:
					self.rollback()
					self.sql("SELECT pg_advisory_unlock(%s)", (lock_key,))
				except Exception:
					pass

	def bulk_insert(self, doctype, fields, values, ignore_duplicates=False, *, chunk_size=10_000):
		"""Stream rows into the table with COPY -- far faster than multi-row INSERT. Falls back to
		the parameterized INSERT path when `ignore_duplicates` is set (COPY has no ON CONFLICT).
		Runs in the current transaction; the caller commits."""
		if ignore_duplicates:
			return super().bulk_insert(doctype, fields, values, ignore_duplicates=True, chunk_size=chunk_size)

		import io

		table_name = get_table_name(doctype)
		# Compose identifiers with psycopg2.sql so a field/table name is always correctly quoted.
		copy_statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
			sql.Identifier(self.db_schema),
			sql.Identifier(table_name),
			sql.SQL(", ").join(sql.Identifier(field) for field in fields),
		)
		if not self._conn:
			self.connect()
		cursor = self._conn.cursor()
		copy_sql = copy_statement.as_string(cursor)
		buffer = io.StringIO()
		try:
			row_count = flushed = 0
			for value in values:
				buffer.write("\t".join(_copy_encode(column) for column in value) + "\n")
				row_count += 1
				if row_count % chunk_size == 0:
					_copy_flush(cursor, copy_sql, buffer)
					# COPY bypasses Database.execute, so keep transaction_writes in step with the
					# rows sent -- else auto_commit_on_many_writes never sees a large load.
					self.transaction_writes += row_count - flushed
					flushed = row_count
			_copy_flush(cursor, copy_sql, buffer)
			self.transaction_writes += row_count - flushed
		finally:
			cursor.close()


def _copy_encode(value):
	"""Encode one value for postgres COPY text format (tab-delimited, ``\\N`` = NULL)."""
	if value is None:
		return r"\N"
	if value is True:
		# Frappe Check fields are smallint, not boolean; smallint_in("true") errors under COPY.
		# "1"/"0" is accepted by both smallint and boolean input functions, matching INSERT.
		return "1"
	if value is False:
		return "0"
	if isinstance(value, datetime.timedelta):
		# Frappe Time fields are timedelta; str() on a >=1 day delta is "1 day, H:MM:SS", which
		# postgres cannot parse as time. Emit HH:MM:SS[.ffffff] so the COPY text is always valid.
		total = int(value.total_seconds())
		hours, remainder = divmod(total, 3600)
		minutes, seconds = divmod(remainder, 60)
		encoded = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
		return f"{encoded}.{value.microseconds:06d}" if value.microseconds else encoded
	return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _copy_flush(cursor, copy_sql, buffer):
	if not buffer.tell():
		return
	buffer.seek(0)
	cursor.copy_expert(copy_sql, buffer)
	buffer.seek(0)
	buffer.truncate(0)


def modify_query(query):
	""" "Modifies query according to the requirements of postgres"""
	# replace ` with " for definitions
	query = str(query).replace("`", '"')
	query = replace_locate_with_strpos(query)
	# MySQL REGEXP operator -> postgres case-insensitive regex match
	query = REGEXP_PATTERN.sub(" ~* ", query)
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
		if isinstance(value, list | tuple):
			value = tuple(modify_values(value))

		elif isinstance(value, int):
			value = str(value)

		return value

	if not values or values == EmptyQueryValues:
		return values

	if isinstance(values, dict):
		# Build a new dict instead of mutating the caller's: callers frequently pass a
		# shared/reused dict as query params (e.g. get_stock_ledger_entries passes the
		# same args dict that the caller keeps reading afterwards). Mutating int values
		# to str in place silently corrupts that dict on postgres only, diverging from
		# mariadb (which has no such transform).
		values = {k: modify_value(v) for k, v in values.items()}
	elif isinstance(values, tuple | list):
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
