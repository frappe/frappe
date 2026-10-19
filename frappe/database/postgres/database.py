import datetime
import re
from contextlib import contextmanager
from itertools import batched

import psycopg
from psycopg import ClientCursor, errors, sql
from psycopg.adapt import AdaptersMap, Dumper, Loader
from psycopg.pq import ExecStatus, TransactionStatus
from psycopg.types.numeric import FloatLoader
from psycopg.types.string import TextLoader

import frappe
from frappe.database.database import CREATE_OR_DROP, DDL_QUERY_TYPES, Database
from frappe.database.postgres.schema import PostgresTable
from frappe.database.utils import EmptyQueryValues, convert_backtick_identifiers, get_query_type
from frappe.utils import cstr, get_table_name


class TimedeltaLoader(Loader):
	"""Load `time` as `timedelta`, which is what frappe models Time fields as (and MariaDB returns)."""

	def load(self, data: bytes | memoryview) -> datetime.timedelta:
		hms, _, frac = bytes(data).decode().partition(".")
		microseconds = int(frac.ljust(6, "0")[:6]) if frac else 0
		hours, minutes, seconds = (int(part) for part in hms.split(":"))
		return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)


class PostgresCursor(psycopg.Cursor):
	"""Describe each result once, by column name and type only.

	psycopg rebuilds full `Column` objects on every access; frappe reads the names several times.
	"""

	_description = None
	_described = None

	@property
	def description(self):
		result = self.pgresult
		if result is not self._described:
			self._described = result
			self._description = None
			if result and (result.nfields or result.status == ExecStatus.TUPLES_OK):
				encoding = self.connection.info.encoding
				self._description = [
					(result.fname(i).decode(encoding), result.ftype(i), None, None, None, None, None)
					for i in range(result.nfields)
				]
		return self._description


class FloatNumericDumper(Dumper):
	"""Send floats as numeric, like the float literals frappe's SQL was written against."""

	oid = psycopg.adapters.types["numeric"].oid

	def dump(self, obj: float) -> bytes:
		return repr(obj).encode()


class CheckDumper(Dumper):
	"""COPY bools as 1/0: Check fields are smallint, which rejects COPY's t/f."""

	def dump(self, obj: bool) -> bytes:
		return b"1" if obj else b"0"


class TimeOfDayDumper(Dumper):
	"""COPY a Time field's timedelta as HH:MM:SS, wrapped to one day like an INSERT into `time`."""

	def dump(self, obj: datetime.timedelta) -> bytes:
		seconds, microseconds = divmod(
			(obj // datetime.timedelta(microseconds=1)) % 86_400_000_000, 1_000_000
		)
		hours, remainder = divmod(seconds, 3600)
		minutes, seconds = divmod(remainder, 60)
		encoded = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
		return (f"{encoded}.{microseconds:06d}" if microseconds else encoded).encode()


class UncopyableDumper(Dumper):
	def dump(self, obj):
		raise TypeError(f"bulk_insert cannot COPY a {type(obj).__name__} value")


COPY_DUMPERS = {
	bool: CheckDumper,
	datetime.timedelta: TimeOfDayDumper,
	list: UncopyableDumper,
	tuple: UncopyableDumper,
	dict: UncopyableDumper,
}

ADAPTERS = AdaptersMap(psycopg.adapters)
ADAPTERS.register_dumper(float, FloatNumericDumper)
ADAPTERS.register_loader("numeric", FloatLoader)
ADAPTERS.register_loader("time", TimedeltaLoader)
# frappe models JSON fields as strings (MariaDB's longtext) and json.loads them on demand
ADAPTERS.register_loader("json", TextLoader)
ADAPTERS.register_loader("jsonb", TextLoader)

# Postgres only accepts bound parameters in these statements; the rest are bound client-side.
SERVER_BOUND_QUERY_TYPES = frozenset(("select", "insert", "update", "delete", "with"))
PLACEHOLDER_PATTERN = re.compile(
	r"%%|(?P<keyword>\b(?P<negated>not\s+)?in\s*)?%(?:\((?P<key>[^)]+)\))?s", flags=re.IGNORECASE
)

LOCATE_SUB_PATTERN = re.compile(r"locate\(([^,]+),([^)]+)(\)?)\)", flags=re.IGNORECASE)
LOCATE_QUERY_PATTERN = re.compile(r"locate\(", flags=re.IGNORECASE)
PG_TRANSFORM_PATTERN = re.compile(r"([=><]+)\s*([+-]?\d+)(\.0)?(?![a-zA-Z\.\d])")
FROM_TAB_PATTERN = re.compile(r"from tab([\w-]*)", flags=re.IGNORECASE)
# MySQL's REGEXP / NOT REGEXP -> postgres `~*` / `!~*` (case-insensitive, matching MySQL's default
# collation). The `skip` branch swallows every token whose contents are data rather than code, so
# the operator is only rewritten where it really is an operator: `SELECT 'a REGEXP b'` keeps its
# text, and a doctype named "My Regexp Rules" keeps its table name (backticks are rewritten to
# double quotes before this runs, so every frappe identifier arrives quoted).
REGEXP_PATTERN = re.compile(
	r"""
	  (?P<skip>
	      (?<!\w)[eE]'(?:[^'\\]|''|\\.)*'    # escape string: a \' does not end it
	    | '(?:[^']|'')*'                     # string literal (only '' escapes a quote)
	    | "(?:[^"]|"")*"                     # quoted identifier
	    | \$(?P<tag>\w*)\$.*?\$(?P=tag)\$    # dollar-quoted string
	    | --[^\n]*                           # line comment
	    | /\*.*?\*/                          # block comment
	  )
	| \s(?P<negated>NOT\s+)?REGEXP\s
	""",
	flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


def _replace_regexp_operator(match: re.Match) -> str:
	if (skipped := match.group("skip")) is not None:
		return skipped
	return " !~* " if match.group("negated") else " ~* "


# Index methods accepted by add_index(using=...): the two custom GIN modes plus postgres'
# native access methods. Anything else is rejected before it reaches the DDL string.
INDEX_METHODS = frozenset({"gin_trgm", "gin_fulltext", "btree", "hash", "gist", "gin", "brin", "spgist"})


class PostgresExceptionUtil:
	ProgrammingError = psycopg.ProgrammingError
	TableMissingError = psycopg.ProgrammingError
	OperationalError = psycopg.OperationalError
	InternalError = psycopg.InternalError
	SQLError = psycopg.ProgrammingError
	DataError = psycopg.DataError
	InterfaceError = psycopg.InterfaceError
	SequenceGeneratorLimitExceeded = errors.SequenceGeneratorLimitExceeded

	@staticmethod
	def is_deadlocked(e):
		# Treat serialization failures like deadlocks: both are retriable transaction-rollback
		# (class 40) errors. Under REPEATABLE READ, a write-write conflict makes MariaDB lock and
		# wait, but postgres aborts the loser with SERIALIZATION_FAILURE ("could not serialize
		# access due to concurrent update"). Classifying it here routes it through frappe's deadlock
		# retry instead of surfacing as an unhandled query error.
		return isinstance(e, errors.DeadlockDetected | errors.SerializationFailure)

	@staticmethod
	def is_timedout(e):
		return isinstance(e, errors.QueryCanceled | errors.LockNotAvailable)

	@staticmethod
	def is_read_only_mode_error(e) -> bool:
		return isinstance(e, errors.ReadOnlySqlTransaction)

	@staticmethod
	def is_syntax_error(e):
		return isinstance(e, errors.SyntaxError)

	@staticmethod
	def is_table_missing(e):
		return isinstance(e, errors.UndefinedTable)

	@staticmethod
	def is_missing_table(e):
		return PostgresDatabase.is_table_missing(e)

	@staticmethod
	def is_missing_column(e):
		return isinstance(e, errors.UndefinedColumn)

	@staticmethod
	def is_access_denied(e):
		return isinstance(e, errors.InsufficientPrivilege)

	@staticmethod
	def cant_drop_field_or_key(e):
		return isinstance(e, errors.IntegrityConstraintViolation)

	@staticmethod
	def is_duplicate_entry(e):
		return isinstance(e, errors.UniqueViolation)

	@staticmethod
	def is_primary_key_violation(e):
		if not PostgresExceptionUtil.is_duplicate_entry(e):
			return False
		return cstr(e.diag.constraint_name).endswith("_pkey")

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
		return isinstance(e, errors.DuplicateColumn)

	@staticmethod
	def is_statement_timeout(e):
		return PostgresDatabase.is_timedout(e) or isinstance(e, frappe.QueryTimeoutError)

	@staticmethod
	def is_data_too_long(e):
		return isinstance(e, errors.StringDataRightTruncation)

	@staticmethod
	def is_data_truncated(e):
		# a value cannot be cast to the column's new type -- e.g. changing a field holding
		# "not a number" to Int. MariaDB reports TRUNCATED_WRONG_VALUE; postgres aborts the ALTER
		# when a value fails the cast (invalid representation / numeric out of range / invalid date
		# or time). A datatype mismatch means a missing USING cast, not bad data, so it stays raw.
		return isinstance(
			e,
			errors.InvalidTextRepresentation
			| errors.NumericValueOutOfRange
			| errors.InvalidDatetimeFormat
			| errors.DatetimeFieldOverflow,
		)

	@staticmethod
	def is_db_table_size_limit(e) -> bool:
		return False

	@staticmethod
	def is_interface_error(e):
		return isinstance(e, psycopg.InterfaceError)


class PostgresDatabase(PostgresExceptionUtil, Database):
	REGEX_CHARACTER = "~"
	MAX_COLUMN_LENGTH = 63
	default_port = "5432"
	_transaction_has_schema_changes = False
	# admin connections set this: CREATE and DROP DATABASE can't run inside a transaction block
	autocommit = False

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
	def db_schema(self):
		return frappe.conf.get("db_schema", "public").replace("'", "").replace('"', "")

	def get_connection(self):
		search_path = self.db_schema.replace("\\", "\\\\").replace(" ", "\\ ")
		conn_settings = {
			"dbname": self.cur_db_name,
			"user": self.user,
			# libpg defaults to default socket if not specified
			"host": self.host or self.socket,
			"options": f"-c search_path={search_path} -c default_transaction_isolation=repeatable\\ read",
		}
		# libpq's GSSAPI (krb5) path is not fork-safe; with the default gssencmode=prefer RQ work
		# horses segfault on fork ("work-horse terminated unexpectedly"). The option exists from
		# libpq 12, so guard on the runtime version (an older client lib would reject it); validate
		# any site-config override against libpq's modes so a bad value can't break every connection.
		if psycopg.pq.version() >= 120000:
			gssencmode = str(frappe.conf.get("db_gssencmode") or "disable")
			if gssencmode not in ("disable", "allow", "prefer", "require"):
				gssencmode = "disable"
			conn_settings["gssencmode"] = gssencmode
		if self.password:
			conn_settings["password"] = self.password
		if not self.socket and self.port:
			conn_settings["port"] = self.port

		# frappe sends its own START TRANSACTION and COMMIT, so psycopg must not add a BEGIN of its
		# own. Connections last one request or job, so prepare early to reuse within one.
		conn = psycopg.connect(
			**conn_settings,
			autocommit=True,
			context=ADAPTERS,
			cursor_factory=PostgresCursor,
			prepare_threshold=2,
		)
		if not self.autocommit:
			conn.execute("START TRANSACTION")

		return conn

	def set_execution_timeout(self, seconds: float):
		# Postgres expects milliseconds as input
		self.sql("set local statement_timeout = %s", round(seconds * 1000))

	def get_execution_timeout(self) -> float:
		query = "select setting::float / 1000 from pg_settings where name = 'statement_timeout'"
		return self.sql(query)[0][0]

	@contextmanager
	def execution_timeout(self, seconds: float):
		"""A timed out statement aborts the transaction, which rejects the restore and ends `set local` anyway."""
		previous_timeout = self.get_execution_timeout()
		self.set_execution_timeout(seconds)
		try:
			yield
		finally:
			if self._conn.info.transaction_status != TransactionStatus.INERROR:
				self.set_execution_timeout(previous_timeout)

	def set_session_time_zone(self, timezone: str):
		self.sql("set time zone %s", timezone)

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

		return sql.quote(s, self._conn)

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
		return super().sql(modify_query(query), values, *args, **kwargs)

	def _transform_query(self, query, values):
		return bind_values(query, values)

	def execute_query(self, query, values=None):
		if values and get_query_type(query) not in SERVER_BOUND_QUERY_TYPES:
			query, values = self.mogrify(query, values), None
		return self._cursor.execute(query, values)

	def mogrify(self, query, values):
		if not values:
			return query
		return ClientCursor(self._conn).mogrify(query, values)

	def log_query(self, query, query_type, values=None, debug=False):
		self.last_query = super().log_query(query, query_type, values, debug)
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

	def clear_db_table_cache(self, query_type: str):
		"""Postgres DDL is transactional, so drop the schema caches on a rollback that follows DDL."""
		if query_type in CREATE_OR_DROP:
			frappe.client_cache.delete_keys("db_tables::*")
		if query_type in DDL_QUERY_TYPES:
			self._transaction_has_schema_changes = True
		elif query_type == "commit":
			self._transaction_has_schema_changes = False
		elif query_type == "rollback" and self._transaction_has_schema_changes:
			# stays set: a rollback to a savepoint keeps the DDL that ran before it
			frappe.client_cache.delete_keys("db_tables::*")
			frappe.client_cache.delete_keys("table_columns::*")

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
		return code == psycopg.NUMBER

	@staticmethod
	def is_type_datetime(code):
		return code == psycopg.DATETIME

	def rename_table(self, old_name: str, new_name: str) -> list | tuple:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		result = self.sql(f"ALTER TABLE `{old_name}` RENAME TO `{new_name}`")
		self.rename_table_indexes(old_name, new_name)
		return result

	def rename_table_indexes(self, old_table: str, new_table: str):
		"""Give indexes named after `old_table` the names they would get on `new_table`."""
		from frappe.database.postgres.schema import get_qualified_index_name

		for index_name, columns in self.get_index_columns(new_table).items():
			for suffix in (None, "unique", *INDEX_METHODS):
				if index_name == get_qualified_index_name(old_table, columns, suffix):
					new_index_name = get_qualified_index_name(new_table, columns, suffix)
					self.sql(f'ALTER INDEX "{self.db_schema}"."{index_name}" RENAME TO "{new_index_name}"')
					break

	def get_index_columns(self, table_name: str) -> dict[str, list[str]]:
		"""Map each index on the table to its key columns, in order."""
		return dict(
			self.sql(
				"""
				SELECT ic.relname, ARRAY(
					SELECT a.attname
					FROM unnest(i.indkey[:i.indnkeyatts - 1]) WITH ORDINALITY AS k(attnum, position)
					JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
					ORDER BY k.position
				)
				FROM pg_index i
				JOIN pg_class tc ON tc.oid = i.indrelid
				JOIN pg_class ic ON ic.oid = i.indexrelid
				JOIN pg_namespace n ON n.oid = tc.relnamespace
				WHERE tc.relname = %s AND n.nspname = %s
				""",
				(table_name, self.db_schema),
			)
		)

	def describe(self, doctype: str) -> list | tuple:
		return self.sql(
			"SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_NAME = %(table_name)s AND table_schema = %(schema)s",
			{"table_name": get_table_name(doctype), "schema": self.db_schema},
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
		catalogs so callers stay db-agnostic. Only full (non-partial) btree indexes count,
		like the indexes SHOW INDEX reports on InnoDB -- a hash or partial index cannot
		serve the ordering and unrestricted lookups callers are checking for.
		``Constraint_name`` is set when a primary key or unique constraint owns the index.
		"""
		result = self.sql(
			f"""
			SELECT ic.relname AS "Key_name", c.conname AS "Constraint_name"
			FROM pg_index i
			JOIN pg_class tc ON tc.oid = i.indrelid
			JOIN pg_class ic ON ic.oid = i.indexrelid
			JOIN pg_am am ON am.oid = ic.relam
			JOIN pg_namespace n ON n.oid = tc.relnamespace
			JOIN pg_attribute a ON a.attrelid = tc.oid AND a.attnum = i.indkey[0]
			LEFT JOIN pg_constraint c
				ON c.conindid = i.indexrelid AND c.conrelid = i.indrelid AND c.contype IN ('p', 'u')
			WHERE tc.relname = %(table_name)s
				AND n.nspname = %(schema)s
				AND a.attname = %(fieldname)s
				AND i.indisunique = {"true" if unique else "false"}
				AND i.indnkeyatts = 1
				AND i.indisvalid
				AND i.indisready
				AND i.indislive
				AND am.amname = 'btree'
				AND i.indpred IS NULL
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
		per *schema*, as postgres requires). A non-default `using`, `where` or `include` adds a
		digest of that definition to the name, so a partial or covering index never shares a name
		with the plain index over the same key columns.

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
		# all but the first, leaving the index missing. Qualify with the table and everything else
		# that makes this index a distinct object -- `using`, the partial predicate and the
		# INCLUDE list -- so no two differing definitions ever share a name.
		index_name = index_name or get_qualified_index_name(
			table_name, clean_fields, using, where=where, include=include
		)
		if self.has_index(table_name, index_name):
			return

		if using == "gin_trgm":
			self.sql_ddl("CREATE EXTENSION IF NOT EXISTS pg_trgm")

		method = f" USING {'gin' if using in ('gin_trgm', 'gin_fulltext') else using}" if using else ""
		include_clause = f""" INCLUDE ("{'", "'.join(include)}")""" if include else ""
		condition = f" WHERE {where}" if where else ""
		self.sql_ddl(
			f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{self.db_schema}"."{table_name}"'
			f"{method} ({self._index_target(clean_fields, using)}){include_clause}{condition}"
		)
		# `search_index` stands for a plain index, so a partial, covering or `using` one must not set it
		if not (using or where or include):
			self.persist_search_index(doctype, fields)

	def persist_search_index(self, doctype: str, fields: list[str]) -> None:
		"""Set `search_index` on a single field indexed outside install or migrate, so alter keeps the index."""
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		if len(fields) != 1 or frappe.flags.in_install or frappe.flags.in_migrate:
			return
		# a raw table, a standard column or a prefix length like `field(10)` has no docfield to mark
		if not self.exists("DocType", doctype) or not frappe.get_meta(doctype).has_field(fields[0]):
			return
		make_property_setter(
			doctype,
			fields[0],
			property="search_index",
			value="1",
			property_type="Check",
			for_doctype=False,  # Applied on docfield
		)

	def _index_target(self, fields: list[str], using: str | None) -> str:
		"""The column list (or functional expression) an index is built over, per `using` mode."""
		if using == "gin_trgm":
			opclass = self.get_trigram_opclass()
			return ", ".join(f'"{field}" {opclass}' for field in fields)
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

	def get_trigram_opclass(self) -> str:
		"""`gin_trgm_ops` qualified with pg_trgm's schema, which may be off the site's search_path."""
		# regnamespace prints the schema name quoted where needed
		schema = self.sql("SELECT extnamespace::regnamespace FROM pg_extension WHERE extname = 'pg_trgm'")
		return f"{schema[0][0]}.gin_trgm_ops"

	def add_unique(self, doctype, fields, constraint_name=None):
		from frappe.database.postgres.schema import get_qualified_index_name

		if isinstance(fields, str):
			fields = [fields]
		if constraint_name:
			legacy_name = constraint_name
		else:
			constraint_name = get_qualified_index_name(get_table_name(doctype), fields, "unique")
			# a table constrained before names were table-qualified still carries the legacy one;
			# recognise it so we don't add a second constraint enforcing the same uniqueness
			legacy_name = "unique_" + "_".join(fields)

		if not self.sql(
			"""
			SELECT CONSTRAINT_NAME
			FROM information_schema.TABLE_CONSTRAINTS
			WHERE table_name=%s
			AND constraint_type='UNIQUE'
			AND constraint_schema=%s
			AND CONSTRAINT_NAME IN (%s, %s)""",
			("tab" + doctype, self.db_schema, constraint_name, legacy_name),
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
		# Only plain btree indexes count: a partial, covering or non-btree index cannot be the
		# framework-managed search index, so reporting it here would both suppress creating the
		# real one and mark a hand-made index as framework-owned and droppable.
		return self.sql(
			"""
			SELECT a.column_name AS name,
			CASE LOWER(a.data_type)
				WHEN 'character varying' THEN CONCAT('varchar(', a.character_maximum_length ,')')
				WHEN 'timestamp without time zone' THEN 'timestamp'
				WHEN 'time without time zone' THEN CONCAT('time(', a.datetime_precision, ')')
				WHEN 'integer' THEN 'int'
				WHEN 'numeric' THEN CONCAT('decimal(', a.numeric_precision, ',', a.numeric_scale, ')')
				ELSE a.data_type
			END AS type,
			COALESCE(BOOL_OR(NOT b.is_unique), false) AS index,
			SPLIT_PART(COALESCE(a.column_default, NULL), '::', 1) AS default,
			COALESCE(BOOL_OR(b.is_unique AND NOT b.is_primary), false) AS unique,
			COALESCE(a.is_nullable = 'NO', false) AS not_nullable,
			COALESCE(a.is_generated = 'ALWAYS', false) AS is_generated
			FROM information_schema.columns a
			LEFT JOIN (
				SELECT att.attname AS column_name,
					i.indisunique AS is_unique,
					i.indisprimary AS is_primary
				FROM pg_index i
				JOIN pg_class tc ON tc.oid = i.indrelid
				JOIN pg_class ic ON ic.oid = i.indexrelid
				JOIN pg_am am ON am.oid = ic.relam
				JOIN pg_namespace n ON n.oid = tc.relnamespace
				JOIN pg_attribute att ON att.attrelid = tc.oid AND att.attnum = i.indkey[0]
				WHERE tc.relname = %(table_name)s AND n.nspname = %(schema)s
					AND am.amname = 'btree'
					AND i.indpred IS NULL
					AND i.indnatts = i.indnkeyatts
			) b ON b.column_name = a.column_name
			WHERE a.table_name = %(table_name)s
				AND a.table_schema = %(schema)s
			GROUP BY a.column_name, a.data_type, a.column_default, a.character_maximum_length, a.is_nullable, a.numeric_precision, a.numeric_scale, a.datetime_precision, a.is_generated;
		""",
			{"table_name": table_name, "schema": self.db_schema},
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

		# Scope to current schema to avoid cross-site estimates.
		# reltuples is -1 until the table has been vacuumed or analyzed.
		count = self.sql(
			"select c.reltuples from pg_class c join pg_namespace n on n.oid = c.relnamespace where c.relname = %s and n.nspname = %s and c.relkind = 'r'",
			(table, self.db_schema),
		)
		return max(cint(count[0][0]), 0) if count else 0

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

	@staticmethod
	def _advisory_lock_key(key) -> int:
		import hashlib

		return int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:8], "big", signed=True)

	def _poll_advisory_lock(self, try_function, key, timeout):
		import time

		from frappe.exceptions import QueryTimeoutError

		lock_key = self._advisory_lock_key(key)
		deadline = time.monotonic() + timeout
		while not self.sql(f"SELECT {try_function}(%s)", (lock_key,))[0][0]:
			if time.monotonic() >= deadline:
				raise QueryTimeoutError(f"Could not acquire advisory lock {key!r} within {timeout}s")
			time.sleep(0.1)
		return lock_key

	def transaction_advisory_lock(self, key, *, timeout=10):
		"""Take an advisory lock that Postgres releases automatically when the current transaction
		commits or rolls back (pg_advisory_xact_lock) -- no explicit unlock, participates in
		deadlock detection alongside row locks, re-entrant within a transaction. Polls up to
		`timeout` seconds, then raises QueryTimeoutError."""
		self._poll_advisory_lock("pg_try_advisory_xact_lock", key, timeout)

	@contextmanager
	def advisory_lock(self, key, *, timeout=10):
		"""Hold a session-level advisory lock for the duration of the `with` block. Session-scoped
		(pg_advisory_lock) so it survives any intermediate commits the caller makes -- a txn-scoped
		lock would release at the first commit. Polls pg_try_advisory_lock up to `timeout` seconds,
		then raises QueryTimeoutError. `key` is hashed to the bigint the lock functions expect."""
		lock_key = self._poll_advisory_lock("pg_try_advisory_lock", key, timeout)
		save_point = f"advisory_lock_{frappe.generate_hash(length=10)}"
		try:
			self.savepoint(save_point)
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
					self._undo_advisory_lock_block(save_point)
					self.sql("SELECT pg_advisory_unlock(%s)", (lock_key,))
				except Exception:
					pass

	def _undo_advisory_lock_block(self, save_point):
		"""Roll back the aborted lock block, keeping the caller's work and savepoints."""
		try:
			self.rollback(save_point=save_point)
		except Exception:
			# the block committed or rolled back, so nothing before it is left to keep
			self.rollback()

	def bulk_insert(self, doctype, fields, values, ignore_duplicates=False, *, chunk_size=10_000):
		"""Stream rows into the table with COPY -- far faster than multi-row INSERT. Falls back to
		the parameterized INSERT path when `ignore_duplicates` is set (COPY has no ON CONFLICT).
		Runs in the current transaction; the caller commits."""
		if ignore_duplicates:
			return super().bulk_insert(doctype, fields, values, ignore_duplicates=True, chunk_size=chunk_size)

		table_name = get_table_name(doctype)
		copy_sql = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
			sql.Identifier(self.db_schema),
			sql.Identifier(table_name),
			sql.SQL(", ").join(sql.Identifier(field) for field in fields),
		)
		if not self._conn:
			self.connect()
		cursor = self._conn.cursor()
		for python_type, dumper in COPY_DUMPERS.items():
			cursor.adapters.register_dumper(python_type, dumper)
		integer_positions = self._get_integer_positions(table_name, fields)
		try:
			for chunk in batched(values, chunk_size, strict=False):
				with cursor.copy(copy_sql) as copy:
					for row in chunk:
						copy.write_row(_integral_floats_as_ints(row, integer_positions))
				# COPY bypasses `sql`, so count each chunk as one write, like an INSERT
				self.transaction_writes += 1
		finally:
			cursor.close()

	def _get_integer_positions(self, table_name: str, fields: list[str]) -> set[int]:
		"""Positions of `fields` that are integer columns, where COPY needs 1.0 sent as 1."""
		integer_columns = self.sql(
			"""SELECT column_name FROM information_schema.columns
			WHERE table_schema = %s AND table_name = %s AND data_type IN ('smallint', 'integer', 'bigint')""",
			(self.db_schema, table_name),
			pluck=True,
		)
		return {position for position, field in enumerate(fields) if field in integer_columns}


def _integral_floats_as_ints(row, integer_positions):
	"""COPY rejects "1.0" for an integer column, where an INSERT casts the numeric."""
	if not integer_positions:
		return row
	row = list(row)
	for position in integer_positions:
		if isinstance(row[position], float) and row[position].is_integer():
			row[position] = int(row[position])
	return row


def modify_query(query):
	""" "Modifies query according to the requirements of postgres"""
	# replace ` with " only where a backtick delimits an identifier
	query = convert_backtick_identifiers(str(query))
	query = replace_locate_with_strpos(query)
	# MySQL REGEXP operator -> postgres case-insensitive regex match
	query = REGEXP_PATTERN.sub(_replace_regexp_operator, query)
	# select from requires ""
	query = FROM_TAB_PATTERN.sub(r'from "tab\1"', query)

	# only find int (with/without signs), ignore decimals (with/without signs), ignore hashes (which start with numbers),
	# drop .0 from decimals and add quotes around them
	#
	# >>> query = "c='abcd' , a >= 45, b = -45.0, c =   40, d=4500.0, e=3500.53, f=40psdfsd, g=9092094312, h=12.00023"
	# >>> re.sub(r"([=><]+)\s*([+-]?\d+)(\.0)?(?![a-zA-Z\.\d])", r"\1 '\2'", query)
	# 	"c='abcd' , a >= '45', b = '-45', c = '40', d= '4500', e=3500.53, f=40psdfsd, g= '9092094312', h=12.00023

	return PG_TRANSFORM_PATTERN.sub(r"\1 '\2'", query)


def bind_values(query, values):
	"""Send ints and bools as untyped strings, so postgres casts them like MariaDB compares loosely.

	`IN %s` becomes `= ANY(%s)`, one statement for any list length; other sequences expand to `(%s, ...)`.
	"""
	if not values:
		return query, values

	named = isinstance(values, dict)
	if not any(isinstance(value, list | tuple) for value in (values.values() if named else values)):
		if named:
			return query, {key: _coerce(value) for key, value in values.items()}
		return query, [_coerce(value) for value in values]

	binder = _SequenceBinder(values)
	return PLACEHOLDER_PATTERN.sub(binder, query), binder.bound


def _coerce(value):
	if isinstance(value, bool):
		return str(int(value))
	if isinstance(value, int):
		return str(value)
	return value


class _SequenceBinder:
	def __init__(self, values):
		self.named = isinstance(values, dict)
		self.values = values if self.named else iter(values)
		self.bound = {} if self.named else []

	def __call__(self, match: re.Match) -> str:
		key = match["key"]
		if match[0] == "%%" or self.named != bool(key):
			return match[0]

		value = self.values[key] if self.named else next(self.values)
		keyword = match["keyword"] or ""
		if (
			keyword
			and isinstance(value, list | tuple)
			and not any(isinstance(v, list | tuple) for v in value)
		):
			operator = "<> ALL" if match["negated"] else "= ANY"
			return f"{operator}({self._placeholder(key, [_coerce(item) for item in value])})"
		return keyword + self._expand(key, value)

	def _expand(self, key, value):
		if not isinstance(value, list | tuple):
			return self._placeholder(key, _coerce(value))
		return (
			"(" + ", ".join(self._expand(key and f"{key}__{i}", item) for i, item in enumerate(value)) + ")"
		)

	def _placeholder(self, key, value):
		if self.named:
			self.bound[key] = value
			return f"%({key})s"
		self.bound.append(value)
		return "%s"


def replace_locate_with_strpos(query):
	# strpos is the locate equivalent in postgres
	if LOCATE_QUERY_PATTERN.search(query):
		query = LOCATE_SUB_PATTERN.sub(r"strpos(\2\3, \1)", query)
	return query
