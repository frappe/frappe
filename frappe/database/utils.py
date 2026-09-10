# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
import typing
from functools import cached_property, wraps
from types import NoneType

import frappe
from frappe.query_builder.builder import MariaDB, Postgres
from frappe.query_builder.functions import Function

if typing.TYPE_CHECKING:
	from frappe.query_builder import DocType

Query = str | MariaDB | Postgres
QueryValues = tuple | list | dict | None

EmptyQueryValues = object()
FallBackDateTimeStr = "0001-01-01 00:00:00.000000"
DefaultOrderBy = "KEEP_DEFAULT_ORDERING"
NestedSetHierarchy = (
	"ancestors of",
	"descendants of",
	"not ancestors of",
	"not descendants of",
	"descendants of (inclusive)",
)

# Spans whose contents are data, not code. Only the backtick span is rewritten; the rest are
# matched to be stepped over -- both so a backtick inside one survives, and so an apostrophe inside
# one cannot pair with the next quote and swallow the identifiers between. Scanned left to right,
# so a quote only opens a span when it is not already inside one. postgres' own literal forms
# (E'...', $tag$...$tag$) need no branch: what reaches here is MySQL-dialect SQL.
SKIPPED_SPAN_PATTERN = re.compile(
	r"""
	  '(?:[^']|'')*'                     # string literal (only '' escapes a quote)
	| "(?:[^"]|"")*"                     # quoted identifier
	| --[^\n]*                           # line comment
	| /\*.*?\*/                          # block comment
	| `(?:[^`]|``)*`                     # backtick identifier: the one span we rewrite
	""",
	re.DOTALL | re.VERBOSE,
)


def convert_backtick_identifiers(query: str) -> str:
	"""Rewrite MySQL-style ```identifier``` quoting as ANSI ``"identifier"``.

	Only backticks that open or close an identifier are translated; one inside any span
	``SKIPPED_SPAN_PATTERN`` matches is content, and survives.
	"""
	if "`" not in query:
		return query

	def translate(match: re.Match) -> str:
		span = match.group()
		if not span.startswith("`"):
			return span  # a literal, an already-ANSI identifier or a comment
		name = span[1:-1].replace("``", "`")  # unescape MySQL's doubled backtick
		return '"{}"'.format(name.replace('"', '""'))  # re-escape for ANSI

	return SKIPPED_SPAN_PATTERN.sub(translate, query)


def is_query_type(query: str, query_type: str | tuple[str]) -> bool:
	return query.lstrip().split(maxsplit=1)[0].lower().startswith(query_type)


def is_pypika_function_object(field: str) -> bool:
	return getattr(field, "__module__", None) == "pypika.functions" or isinstance(field, Function)


def get_doctype_name(table_name: str) -> str:
	if table_name.startswith(("tab", "`tab", '"tab')):
		table_name = table_name.replace("tab", "", 1)
	table_name = table_name.replace("`", "")
	return table_name.replace('"', "")


class LazyString:
	def _setup(self) -> None:
		raise NotImplementedError

	@cached_property
	def value(self) -> str:
		return self._setup()

	def __str__(self) -> str:
		return self.value

	def __repr__(self) -> str:
		return f"'{self.value}'"


class LazyDecode(LazyString):
	__slots__ = ()

	def __init__(self, value: str) -> None:
		self._value = value

	def _setup(self) -> None:
		return self._value.decode()


class LazyMogrify(LazyString):
	__slots__ = ()

	def __init__(self, query, values) -> None:
		self.query = query
		self.values = values

	def _setup(self) -> str:
		return frappe.db.mogrify(self.query, self.values)


def dangerously_reconnect_on_connection_abort(func):
	"""Reconnect on connection failure.

	As the name suggest, it's dangerous to use this function as it will NOT restore DB transaction
	so make sure you're using it right.

	Ideal use case: Some kinda logging or final steps in a background jobs. Anything more than that
	will risk bugs from DB transactions.
	"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except Exception as e:
			if frappe.db.is_interface_error(e) or isinstance(e, frappe.db.OperationalError):
				frappe.db.connect()
				return func(*args, **kwargs)
			raise

	return wrapper


def drop_index_if_exists(table: str, index: str):
	import click

	if not frappe.db.has_index(table, index):
		click.echo(f"- Skipped {index} index for {table} because it doesn't exist")
		return

	try:
		if frappe.db.db_type == "postgres":
			# Postgres drops indexes with DROP INDEX, not ALTER TABLE ... DROP INDEX
			safe_index = index.replace('"', '""')
			frappe.db.sql_ddl(f'DROP INDEX IF EXISTS "{safe_index}"')
		else:
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` DROP INDEX `{index}`")
	except Exception as e:
		frappe.log_error("Failed to drop index")
		click.secho(f"x Failed to drop index {index} from {table}\n {e!s}", fg="red")
		return

	click.echo(f"✓ dropped {index} index from {table}")
