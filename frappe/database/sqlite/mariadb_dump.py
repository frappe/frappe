import contextlib
import gzip
import hashlib
import math
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pymysql.converters import escape_string

import frappe
from frappe import _
from frappe.database.mariadb.database import MariaDBDatabase
from frappe.database.mariadb.schema import MariaDBTable
from frappe.database.sequence import SQLITE_SEQUENCE_TABLE
from frappe.utils import scrub

FRAMEWORK_SQL = Path(frappe.__file__).parent / "database" / "mariadb" / "framework_mariadb.sql"
FTS_SHADOW_SUFFIXES = ("_config", "_content", "_data", "_docsize", "_idx")
NUMERIC_TYPES = {
	"tinyint",
	"smallint",
	"mediumint",
	"int",
	"integer",
	"bigint",
	"decimal",
	"numeric",
	"float",
	"double",
}
TEMPORAL_TYPES = {"date", "datetime", "time", "timestamp", "year"}
UNINDEXABLE_TYPES = {
	"tinytext",
	"text",
	"mediumtext",
	"longtext",
	"tinyblob",
	"blob",
	"mediumblob",
	"longblob",
	"json",
}
CATALOG_DISPLAY_WIDTHS = {
	"tinyint": "tinyint(4)",
	"smallint": "smallint(6)",
	"int": "int(11)",
	"bigint": "bigint(20)",
}
TEXT_INDEX_PREFIX = 140
MAX_STATEMENT_BYTES = 1024 * 1024
MAX_REPORTED_PROBLEMS = 25
RESTORE_SQL_MODE = (
	"STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,NO_AUTO_VALUE_ON_ZERO"
)
TABLE_OPTIONS = "ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci"


class MariaDBDumpError(frappe.ValidationError):
	pass


class DDLRecorder(MariaDBDatabase):
	"""Stands in for `frappe.db` so MariaDB schema code records its DDL instead of running it.

	It behaves like a new, empty MariaDB database: catalog queries find nothing, so schema code
	takes its "create" path. Reads are answered by `source`, the site's SQLite connection, and
	writes are dropped so schema hooks cannot change the site being backed up.
	"""

	def __init__(self, source):
		super().__init__()
		self.source = source
		self.statements: list[str] = []
		self.dropped_writes: list[str] = []
		self.catalog: dict[str, TableShape] = {}

	def sql(self, query, *args, **kwargs):
		text = str(query).strip()
		lowered = text.lower()
		if is_ddl(lowered):
			self.statements.append(text)
			return ()
		if "information_schema" in lowered or lowered.startswith("show"):
			return ()
		if lowered.startswith(("select", "with", "pragma", "explain")):
			return self.source.sql(query, *args, **kwargs)
		self.dropped_writes.append(text)
		return ()

	def sql_ddl(self, query, *args, **kwargs):
		self.statements.append(str(query).strip())

	def get_db_table_columns(self, table) -> list[str]:
		return self.source.get_db_table_columns(table)

	def get_table_columns_description(self, table_name):
		shape = self.catalog.get(table_name)
		return shape.describe_columns() if shape else []

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False):
		shape = self.catalog.get(table_name)
		index = shape.find_column_index(fieldname, unique) if shape else None
		return frappe._dict(Key_name=index.name) if index else None

	def get_column_type(self, doctype, column):
		shape = self.catalog.get(f"tab{doctype}")
		return shape.columns[column].catalog_type if shape and column in shape.columns else None

	def get_tables(self, cached=True):
		return []

	def commit(self, chain=None):
		pass


@contextlib.contextmanager
def recording_mariadb_ddl():
	source = frappe.local.db
	recorder = DDLRecorder(source)
	frappe.local.db = recorder
	try:
		yield recorder
	finally:
		frappe.local.db = source


def is_ddl(query) -> bool:
	return str(query).lstrip().lower().startswith(("create", "alter", "drop"))


@dataclass
class Column:
	name: str
	definition: str

	@property
	def base_type(self) -> str:
		return re.match(r"[a-z]+", self.definition.lower()).group(0)

	@property
	def is_numeric(self) -> bool:
		return self.base_type in NUMERIC_TYPES

	@property
	def is_temporal(self) -> bool:
		return self.base_type in TEMPORAL_TYPES

	@property
	def is_nullable(self) -> bool:
		definition = self.definition.lower()
		return "not null" not in definition and "primary key" not in definition

	@property
	def max_length(self) -> int | None:
		if match := re.match(r"(?:var)?char\((\d+)\)", self.definition.lower()):
			return int(match.group(1))
		return None

	@property
	def catalog_type(self) -> str:
		"""The type as `information_schema.columns.column_type` reports it."""
		declared = re.match(r"[a-z]+(?:\([^)]*\))?", self.definition.lower()).group(0)
		return CATALOG_DISPLAY_WIDTHS.get(declared, declared)

	@property
	def default(self) -> str | None:
		"""The default as `information_schema.columns.column_default` reports it."""
		match = re.search(r"\bdefault\s+('(?:[^'\\]|\\.|'')*'|[^\s,]+)", self.definition, re.I)
		if not match or match.group(1).upper() == "NULL":
			return None
		return match.group(1)


@dataclass
class Index:
	name: str
	columns: tuple[str, ...]
	unique: bool = False
	fulltext: bool = False


@dataclass
class TableShape:
	"""The columns and keys of one MariaDB table, read from its `CREATE TABLE` statement."""

	name: str
	columns: dict[str, Column] = field(default_factory=dict)
	primary_key: tuple[str, ...] = ()
	indexes: list[Index] = field(default_factory=list)

	@property
	def distinct_keys(self) -> list[tuple[str, ...]]:
		unique = [index.columns for index in self.indexes if index.unique]
		keys = [self.primary_key, *unique] if self.primary_key else unique
		return list(dict.fromkeys(keys))

	def covers_index(self, columns: tuple[str, ...]) -> bool:
		return columns == self.primary_key or any(index.columns == columns for index in self.indexes)

	def add_index(self, name: str | None, columns: tuple[str, ...], unique=False, fulltext=False):
		self.indexes.append(Index(name or columns[0], columns, unique, fulltext))

	def drop_index(self, name: str):
		self.indexes = [index for index in self.indexes if index.name != name]

	def find_column_index(self, column: str, unique: bool) -> Index | None:
		"""Mirror of `MariaDBDatabase.get_column_index`: a single-column index on `column`."""
		for index in self.indexes:
			if index.columns == (column,) and index.unique == unique and not index.fulltext:
				return index
		return None

	def describe_columns(self) -> list[frappe._dict]:
		"""Rows in the shape `MariaDBDatabase.get_table_columns_description` returns."""
		rows = []
		for column in self.columns.values():
			rows.append(
				frappe._dict(
					name=column.name,
					type=column.catalog_type,
					default=column.default,
					index=int(
						any(
							index.columns[0] == column.name and not index.unique and not index.fulltext
							for index in self.indexes
						)
					),
					unique=int(self.find_column_index(column.name, unique=True) is not None),
					not_nullable=int(not column.is_nullable or (column.name,) == self.primary_key),
					is_generated=0,
				)
			)
		return rows


def parse_table_shape(create_statement: str) -> TableShape:
	match = re.match(
		r"\s*create\s+table\s+(?:if\s+not\s+exists\s+)?`?([^`(\s]+(?:[^`(]*[^`(\s])?)`?\s*\(",
		create_statement,
		re.I,
	)
	shape = TableShape(name=match.group(1))
	body = create_statement[match.end() : find_closing_parenthesis(create_statement, match.end() - 1)]
	for part in split_top_level(body):
		add_definition(shape, part.strip())
	return shape


def add_definition(shape: TableShape, part: str):
	lowered = part.lower()
	if lowered.startswith("primary key"):
		shape.primary_key = parse_key_columns(part)
	elif lowered.startswith(("unique", "index", "key", "fulltext")):
		shape.add_index(
			parse_index_name(part),
			parse_key_columns(part),
			unique=lowered.startswith("unique"),
			fulltext=lowered.startswith("fulltext"),
		)
	elif not lowered.startswith("constraint"):
		name, definition = split_column_definition(part)
		shape.columns[name] = Column(name, definition)
		if re.search(r"\bprimary\s+key\b", definition, re.I):
			shape.primary_key = (name,)
		elif re.search(r"\bunique\b", definition, re.I):
			shape.add_index(name, (name,), unique=True)


def parse_index_name(part: str) -> str | None:
	"""The name in `UNIQUE [INDEX|KEY] [IF NOT EXISTS] name (...)`, or None when unnamed."""
	match = re.match(
		r"\s*(?:unique|fulltext)?\s*(?:index|key)?\s*(?:if\s+not\s+exists\s+)?(`[^`]+`|[^\s(`]+)?\s*\(",
		part,
		re.I,
	)
	name = match.group(1) if match else None
	if not name or name.lower() in ("unique", "index", "key", "fulltext"):
		return None
	return name.strip("`")


def split_column_definition(part: str) -> tuple[str, str]:
	if part.startswith("`"):
		end = part.index("`", 1)
		return part[1:end], part[end + 1 :].strip()
	name, _, definition = part.partition(" ")
	return name, definition.strip()


def parse_key_columns(part: str) -> tuple[str, ...]:
	start = part.index("(")
	columns = part[start + 1 : find_closing_parenthesis(part, start)]
	return tuple(re.sub(r"\(\d+\)$", "", column.strip()).strip("`") for column in split_top_level(columns))


def find_closing_parenthesis(text: str, start: int) -> int:
	depth = 0
	quote = None
	for index in range(start, len(text)):
		character = text[index]
		if quote:
			if character == quote and text[index - 1] != "\\":
				quote = None
		elif character in "'\"`":
			quote = character
		elif character == "(":
			depth += 1
		elif character == ")":
			depth -= 1
			if depth == 0:
				return index
	raise ValueError(f"Unbalanced parentheses in: {text[:200]}")


def split_top_level(text: str) -> list[str]:
	parts, current, depth, quote = [], [], 0, None
	for index, character in enumerate(text):
		if quote:
			if character == quote and text[index - 1] != "\\":
				quote = None
		elif character in "'\"`":
			quote = character
		elif character == "(":
			depth += 1
		elif character == ")":
			depth -= 1
		elif character == "," and depth == 0:
			parts.append("".join(current))
			current = []
			continue
		current.append(character)
	if "".join(current).strip():
		parts.append("".join(current))
	return parts


def quote_identifier(name: str) -> str:
	return "`" + name.replace("`", "``") + "`"


def quote_sqlite_identifier(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def mariadb_type_for_sqlite(declared_type: str) -> str:
	"""Map a SQLite declared column type to the MariaDB type Frappe would use for it."""
	declared = (declared_type or "").strip().lower()
	if match := re.fullmatch(r"(var)?char\s*\(\s*(\d+)\s*\)", declared):
		return f"varchar({match.group(2)})"
	base = re.match(r"[a-z]*", declared).group(0)
	return {
		"int": "int(11)",
		"integer": "bigint(20)",
		"bigint": "bigint(20)",
		"tinyint": "tinyint(4)",
		"real": "decimal(21,9)",
		"float": "decimal(21,9)",
		"double": "decimal(21,9)",
		"decimal": "decimal(21,9)",
		"numeric": "decimal(21,9)",
		"timestamp": "datetime(6)",
		"datetime": "datetime(6)",
		"date": "date",
		"time": "time(6)",
		"uuid": "uuid",
		"blob": "longblob",
	}.get(base, "longtext")


def collation_key(value):
	"""Approximate `utf8mb4_unicode_ci` equality: case, accents and trailing spaces are ignored."""
	if not isinstance(value, str):
		return value
	decomposed = unicodedata.normalize("NFKD", value)
	return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().rstrip(" ")


def apply_alter_table(shape: TableShape, statement: str):
	"""Record the columns and keys an `ALTER TABLE` adds, modifies or drops."""
	clause_end = r"(.+?)(?=,\s*(?:add|modify|drop)\b|$)"
	for name, definition in re.findall(
		r"\badd\s+column\s+(?:if\s+not\s+exists\s+)?`?([^`\s]+)`?\s+" + clause_end, statement, re.I | re.S
	):
		shape.columns.setdefault(name, Column(name, definition.strip()))
	for name, definition in re.findall(
		r"\bmodify\s+(?:column\s+)?`?([^`\s]+)`?\s+" + clause_end, statement, re.I | re.S
	):
		shape.columns[name] = Column(name, definition.strip())
	for name in re.findall(r"\bdrop\s+(?:index|key)\s+(?:if\s+exists\s+)?`?([^`\s,]+)`?", statement, re.I):
		shape.drop_index(name)
	for match in re.finditer(
		r"\badd\s+(unique\s+)?(?:index|key)?\s*(?:if\s+not\s+exists\s+)?(`[^`]*`|\w+)?\s*\(",
		statement,
		re.I,
	):
		start = match.end() - 1
		key = parse_key_columns(statement[start : find_closing_parenthesis(statement, start) + 1])
		name = (match.group(2) or "").strip("`") or None
		shape.add_index(name, key, unique=bool(match.group(1)))


def framework_table_statements() -> dict[str, str]:
	text = FRAMEWORK_SQL.read_text()
	statements = re.findall(r"(CREATE TABLE `([^`]+)` \(.*?\) ENGINE=[^;]*);", text, re.S)
	return {name: statement for statement, name in statements}


class MariaDBDumpWriter:
	"""Write the site's SQLite database as a MariaDB SQL script that `bench restore` can import."""

	def __init__(self, database_path, include_tables=None, exclude_tables=None, verbose=False):
		self.database_path = Path(database_path)
		self.include_tables = set(include_tables or [])
		self.exclude_tables = set(exclude_tables or [])
		self.verbose = verbose
		self.problems: list[str] = []
		self.warnings: list[str] = []
		self.doctypes = set(
			frappe.get_all("DocType", filters={"issingle": 0, "is_virtual": 0}, pluck="name", order_by="name")
		)
		self.framework_tables = framework_table_statements()

	def write(self, path, header: str):
		with self.snapshot() as connection, gzip.open(path, "wt", encoding="utf-8") as dump:
			dump.write(header)
			dump.write(f"SET NAMES utf8mb4;\nSET SESSION sql_mode='{RESTORE_SQL_MODE}';\n")
			dump.write("SET FOREIGN_KEY_CHECKS=0;\nSET AUTOCOMMIT=0;\n\n")
			for table in self.get_tables(connection):
				self.write_table(connection, dump, table)
			self.write_sequences(connection, dump)
			dump.write("COMMIT;\nSET FOREIGN_KEY_CHECKS=1;\n")
		for warning in self.warnings:
			if self.verbose:
				print(warning)
		if self.problems:
			self.raise_problems()

	@contextlib.contextmanager
	def snapshot(self):
		connection = sqlite3.connect(f"file:{self.database_path}?mode=ro", uri=True, timeout=15)
		connection.text_factory = str
		try:
			connection.execute("BEGIN")
			connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
			yield connection
		finally:
			connection.rollback()
			connection.close()

	def get_tables(self, connection) -> list[str]:
		rows = connection.execute(
			"SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
		).fetchall()
		virtual = [name for name, sql in rows if (sql or "").upper().startswith("CREATE VIRTUAL TABLE")]
		shadow = {f"{name}{suffix}" for name in virtual for suffix in FTS_SHADOW_SUFFIXES}
		tables = [
			name
			for name, _sql in rows
			if not name.startswith("sqlite_") and name != SQLITE_SEQUENCE_TABLE and name not in shadow
		]
		if self.include_tables:
			tables = [table for table in tables if table in self.include_tables]
		return [table for table in tables if table not in self.exclude_tables]

	def write_table(self, connection, dump, table: str):
		statements = self.get_create_statements(connection, table)
		create_table = next(
			statement for statement in statements if statement.lower().startswith("create table")
		)
		shape = parse_table_shape(create_table)
		for statement in statements:
			if statement.lower().startswith("alter table"):
				apply_alter_table(shape, statement)
		source_columns = get_sqlite_columns(connection, table)

		dump.write(f"--\n-- Table structure for table {quote_identifier(table)}\n--\n\n")
		dump.write(f"DROP TABLE IF EXISTS {quote_identifier(table)};\n")
		for statement in statements:
			dump.write(f"{statement};\n")
		for column in self.add_missing_columns(dump, table, shape, source_columns):
			shape.columns[column.name] = column
		self.write_extra_indexes(connection, dump, table, shape)
		dump.write("\n")
		self.write_rows(
			connection, dump, table, shape, [column for column, _type, _notnull in source_columns]
		)

	def get_create_statements(self, connection, table: str) -> list[str]:
		if table.startswith("tab") and table[3:] in self.doctypes:
			return self.get_doctype_statements(table[3:])
		if table in self.framework_tables:
			return [self.framework_tables[table]]
		if table == "__global_search":
			with recording_mariadb_ddl() as recorder:
				recorder.create_global_search_table()
			return recorder.statements
		if table == "__UserSettings":
			with recording_mariadb_ddl() as recorder:
				recorder.create_user_settings_table()
			return recorder.statements
		return [self.translate_table(connection, table)]

	def get_doctype_statements(self, doctype: str) -> list[str]:
		"""The DDL a MariaDB site ends up with for this DocType after install and migrate."""
		meta = frappe.get_meta(doctype, False)
		with recording_mariadb_ddl() as recorder:
			table = MariaDBTable(doctype, meta)
			if framework_statement := self.framework_tables.get(table.table_name):
				recorder.statements.append(framework_statement)
				recorder.catalog[table.table_name] = parse_table_shape(framework_statement)
				table.setup_table_columns()
				table.alter()
			else:
				table.create()
			self.run_doctype_update_hook(meta)
		if recorder.dropped_writes:
			self.warnings.append(
				f"Ignored writes from the schema hooks of {doctype}: {recorder.dropped_writes}"
			)
		return recorder.statements

	def run_doctype_update_hook(self, meta):
		"""Run `on_doctype_update`, as DocType sync does, so hook-made MariaDB DDL is included."""
		from frappe.modules import load_doctype_module

		if meta.custom:
			return
		try:
			module = load_doctype_module(meta.name, meta.module)
		except ImportError:
			self.warnings.append(
				f"Could not load the controller of {meta.name}; its schema hooks were not run."
			)
			return
		if hook := getattr(module, "on_doctype_update", None):
			in_migrate = frappe.flags.in_migrate
			frappe.flags.in_migrate = True
			try:
				hook()
			finally:
				frappe.flags.in_migrate = in_migrate

	def translate_table(self, connection, table: str) -> str:
		"""Fallback for tables no DocType or framework definition describes."""
		columns = connection.execute(f"PRAGMA table_info({quote_sqlite_identifier(table)})").fetchall()
		primary_key = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
		definitions = []
		for _cid, name, declared_type, not_null, default, pk in columns:
			definition = mariadb_type_for_sqlite(declared_type)
			if pk and definition in ("longtext", "longblob"):
				definition = "varchar(255)"
			if not_null or pk:
				definition += " NOT NULL"
			if default is not None and re.fullmatch(r"-?\d+(\.\d+)?|'(?:[^']|'')*'", str(default)):
				definition += f" DEFAULT {default}"
			definitions.append(f"{quote_identifier(name)} {definition}")
		if primary_key:
			definitions.append(f"PRIMARY KEY ({', '.join(map(quote_identifier, primary_key))})")
		self.warnings.append(f"Table {table} has no DocType; its schema was translated from SQLite.")
		return (
			f"CREATE TABLE {quote_identifier(table)} (\n\t"
			+ ",\n\t".join(definitions)
			+ f"\n) {TABLE_OPTIONS}"
		)

	def add_missing_columns(self, dump, table: str, shape: TableShape, source_columns) -> list[Column]:
		added = []
		for name, declared_type, _notnull in source_columns:
			if name in shape.columns:
				continue
			column = Column(name, mariadb_type_for_sqlite(declared_type))
			dump.write(
				f"ALTER TABLE {quote_identifier(table)} ADD COLUMN {quote_identifier(name)} {column.definition};\n"
			)
			added.append(column)
		return added

	def write_extra_indexes(self, connection, dump, table: str, shape: TableShape):
		for _seq, index_name, unique, origin, partial in connection.execute(
			f"PRAGMA index_list({quote_sqlite_identifier(table)})"
		).fetchall():
			if origin == "pk":
				continue
			if partial:
				self.warnings.append(
					f"Skipped partial index {index_name} on {table}: MariaDB has no partial indexes;"
					" the DocType's schema hook provides the MariaDB equivalent."
				)
				continue
			columns = tuple(
				row[2]
				for row in connection.execute(f"PRAGMA index_info({quote_sqlite_identifier(index_name)})")
			)
			if not columns or None in columns or shape.covers_index(columns):
				continue
			text_columns = [
				column for column in columns if shape.columns[column].base_type in UNINDEXABLE_TYPES
			]
			if unique and text_columns:
				self.warnings.append(
					f"Skipped unique index {index_name} on {table}: a prefix of {text_columns} would change what is unique."
				)
				continue
			index_columns = ", ".join(
				quote_identifier(column) + (f"({TEXT_INDEX_PREFIX})" if column in text_columns else "")
				for column in columns
			)
			kind = "UNIQUE INDEX" if unique else "INDEX"
			dump.write(
				f"CREATE {kind} IF NOT EXISTS {quote_identifier(mariadb_index_name(table, index_name))} "
				f"ON {quote_identifier(table)} ({index_columns});\n"
			)
			shape.add_index(mariadb_index_name(table, index_name), columns, unique=bool(unique))

	def write_rows(self, connection, dump, table: str, shape: TableShape, columns: list[str]):
		if not columns:
			return
		target_columns = [shape.columns[column] for column in columns]
		keys = [
			(key, [columns.index(column) for column in key])
			for key in shape.distinct_keys
			if set(key) <= set(columns)
		]
		seen_keys = [{} for _ in keys]
		prefix = (
			f"INSERT INTO {quote_identifier(table)} ({', '.join(map(quote_identifier, columns))}) VALUES\n"
		)
		cursor = connection.execute(
			f"SELECT {', '.join(map(quote_sqlite_identifier, columns))} FROM {quote_sqlite_identifier(table)}"
		)
		batch, batch_bytes = [], 0
		while rows := cursor.fetchmany(1000):
			for row in rows:
				self.check_keys(table, keys, seen_keys, row)
				values = (
					"("
					+ ",".join(
						self.literal(table, row, value, column)
						for value, column in zip(row, target_columns, strict=True)
					)
					+ ")"
				)
				batch.append(values)
				batch_bytes += len(values)
				if batch_bytes >= MAX_STATEMENT_BYTES:
					dump.write(prefix + ",\n".join(batch) + ";\n")
					batch, batch_bytes = [], 0
		if batch:
			dump.write(prefix + ",\n".join(batch) + ";\n")
		dump.write("\n")

	def check_keys(self, table: str, keys, seen_keys, row):
		for (key, positions), seen in zip(keys, seen_keys, strict=True):
			values = tuple(row[position] for position in positions)
			if None in values:
				continue
			collated = tuple(collation_key(value) for value in values)
			if (first := seen.setdefault(collated, values)) != values:
				self.add_problem(
					_(
						"{0}: {1} values {2} and {3} are equal under MariaDB's case- and accent-insensitive collation"
					).format(table, "/".join(key), first, values)
				)

	def literal(self, table: str, row, value, column: Column) -> str:
		value = self.coerce(table, row, value, column)
		if value is None:
			return "NULL"
		if isinstance(value, bool):
			return "1" if value else "0"
		if isinstance(value, int | Decimal):
			return str(value)
		if isinstance(value, float):
			if not math.isfinite(value):
				self.add_problem(
					_("{0}.{1}: {2} cannot be stored in MariaDB").format(table, column.name, value)
				)
				return "NULL"
			return repr(value)
		if isinstance(value, bytes):
			return f"X'{value.hex()}'" if value else "''"
		return "'" + escape_string(str(value)) + "'"

	def coerce(self, table: str, row, value, column: Column):
		if isinstance(value, str):
			if column.is_numeric:
				return self.coerce_number(table, row, value, column)
			if column.base_type == "date" and re.fullmatch(r"\d{4}-\d\d-\d\d[ T].*", value):
				return value[:10]
			if column.is_temporal and not value.strip():
				return (
					None
					if column.is_nullable
					else self.add_problem(
						_("{0}.{1}: empty value in a NOT NULL date/time column (row {2})").format(
							table, column.name, row[0]
						)
					)
				)
			if (max_length := column.max_length) and len(value) > max_length:
				self.add_problem(
					_("{0}.{1}: value of {2} characters exceeds {3} (row {4})").format(
						table, column.name, len(value), column.definition, row[0]
					)
				)
		return value

	def coerce_number(self, table: str, row, value: str, column: Column):
		text = value.strip()
		if not text:
			return None if column.is_nullable else 0
		try:
			number = Decimal(text)
		except InvalidOperation:
			number = None
		if number is not None and number.is_finite():
			return number
		self.add_problem(
			_("{0}.{1}: {2!r} is not a number (row {3})").format(table, column.name, value, row[0])
		)
		return None

	def write_sequences(self, connection, dump):
		sequences = {}
		if self.has_table(connection, SQLITE_SEQUENCE_TABLE):
			sequences = {
				row[0]: row
				for row in connection.execute(
					f"SELECT name, current, increment, min_value, max_value, cycle FROM {SQLITE_SEQUENCE_TABLE}"
				)
			}
		dumped_tables = set(self.get_tables(connection))
		autoincrement_doctypes = frappe.get_all(
			"DocType", filters={"issingle": 0, "is_virtual": 0, "autoname": "autoincrement"}, pluck="name"
		)
		dump.write("--\n-- Sequences\n--\n\n")
		for doctype in sorted(autoincrement_doctypes):
			if f"tab{doctype}" not in dumped_tables:
				continue
			name = scrub(f"{doctype}_id_seq")
			row = sequences.pop(name, None)
			current = max(row[1] if row else 0, highest_numeric_name(connection, f"tab{doctype}"))
			if current:
				dump.write(f"SELECT SETVAL({quote_identifier(name)}, {int(current)}, 1);\n")
		if not self.include_tables:
			for name, current, increment, min_value, max_value, cycle in sequences.values():
				options = f" INCREMENT BY {increment} MINVALUE {min_value}"
				options += f" MAXVALUE {max_value}" if max_value is not None else ""
				options += " CYCLE" if cycle else " NOCYCLE"
				dump.write(f"CREATE SEQUENCE IF NOT EXISTS {quote_identifier(name)}{options} NOCACHE;\n")
				dump.write(f"SELECT SETVAL({quote_identifier(name)}, {int(current)}, 1);\n")
		dump.write("\n")

	@staticmethod
	def has_table(connection, table: str) -> bool:
		return bool(
			connection.execute(
				"SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
			).fetchone()
		)

	def add_problem(self, message: str):
		self.problems.append(message)

	def raise_problems(self):
		shown = self.problems[:MAX_REPORTED_PROBLEMS]
		more = len(self.problems) - len(shown)
		details = "\n".join(f"- {problem}" for problem in shown)
		if more:
			details += "\n" + _("... and {0} more").format(more)
		frappe.throw(
			_(
				"The database cannot be restored on MariaDB as it is. Fix these values and take the backup again:"
			)
			+ "\n"
			+ details,
			exc=MariaDBDumpError,
			title=_("MariaDB-compatible backup failed"),
		)


def get_sqlite_columns(connection, table: str) -> list[tuple[str, str, int]]:
	return [
		(row[1], row[2], row[3])
		for row in connection.execute(f"PRAGMA table_info({quote_sqlite_identifier(table)})").fetchall()
	]


def highest_numeric_name(connection, table: str) -> int:
	row = connection.execute(
		f"SELECT max(CAST(name AS INTEGER)) FROM {quote_sqlite_identifier(table)} WHERE name GLOB '[0-9]*'"
	).fetchone()
	return int(row[0] or 0)


def mariadb_index_name(table: str, name: str) -> str:
	"""The name MariaDB's `add_index` / `add_unique` would have given this SQLite index.

	SQLite prefixes index names with the table, MariaDB does not; matching the native name lets
	hooks that later re-add the index find it instead of creating a duplicate.
	"""
	name = name.removeprefix(f"{table}_")
	if len(name) <= 64:
		return name
	return name[:55] + "_" + hashlib.sha1(name.encode()).hexdigest()[:8]


def write_mariadb_dump(
	database_path, path, header: str, include_tables=None, exclude_tables=None, verbose=False
):
	MariaDBDumpWriter(database_path, include_tables, exclude_tables, verbose).write(path, header)
