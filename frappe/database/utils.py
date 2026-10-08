# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
import string
from collections.abc import KeysView, ValuesView
from functools import cached_property, wraps

import frappe
from frappe.query_builder.builder import MariaDB, Postgres, SQLite
from frappe.query_builder.functions import Function
from frappe.utils import CallbackManager

Query = str | MariaDB | Postgres | SQLite
QueryValues = tuple | list | dict | None
FilterValue = str | int | bool

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
# split when non-alphabetical character is found
QUERY_TYPE_PATTERN = re.compile(r"\s*([A-Za-z]*)")

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


def convert_to_value(o: FilterValue):
	if isinstance(o, bool):
		return int(o)
	elif isinstance(o, dict):
		return frappe.as_json(o)
	elif isinstance(o, (KeysView, ValuesView)):
		return tuple(convert_to_value(item) for item in o)
	return o


def get_query_type(query: str) -> str:
	return QUERY_TYPE_PATTERN.match(query)[1].lower()


def is_query_type(query: str, query_type: str | tuple[str, ...]) -> bool:
	return get_query_type(query).startswith(query_type)


def is_pypika_function_object(field: str) -> bool:
	return getattr(field, "__module__", None) == "pypika.functions" or isinstance(field, Function)


def get_doctype_name(table_name: str) -> str:
	if table_name.startswith(("tab", "`tab", '"tab')):
		table_name = table_name.replace("tab", "", 1)
	table_name = table_name.replace("`", "")
	return table_name.replace('"', "")


def get_doctype_sort_info(doctype: str) -> tuple[str, str]:
	"""
	Get sort_field and sort_order for a DocType from meta.

	Args:
		doctype: The DocType name

	Returns:
		Tuple of (sort_field, sort_order) with defaults ("creation", "DESC") if not found
	"""
	from frappe.database.query import CORE_DOCTYPES

	if doctype in CORE_DOCTYPES:
		return "creation", "DESC"

	try:
		meta = frappe.get_meta(doctype)
		return meta.sort_field or "creation", meta.sort_order or "DESC"
	except frappe.DoesNotExistError:
		return "creation", "DESC"


class LazyString:
	def _setup(self) -> str:
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

	def _setup(self) -> str:
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


class CommitAfterResponseManager(CallbackManager):
	__slots__ = ()

	def run(self):
		db = getattr(frappe.local, "db", None)
		if not db:
			# try reconnecting to the database
			frappe.connect(set_admin_as_user=False)
			db = frappe.local.db

		savepoint_name = "commit_after_response"

		while self._functions:
			_func = self._functions.popleft()
			try:
				db.savepoint(savepoint_name)
				_func()
			except Exception:
				db.rollback(save_point=savepoint_name)
				frappe.log_error(title="Error executing commit_after_response callback")

		db.commit()  # nosemgrep


def commit_after_response(func):
	"""
	Runs and commits some queries after response is sent.
	Works only if in a request context and not in tests.
	Calls function immediately otherwise.
	"""

	request = getattr(frappe.local, "request", False)
	if not request or frappe.in_test:
		func()
		return

	callback_manager = getattr(request, "commit_after_response", None)
	if callback_manager is None:
		# if no callback manager, create one
		callback_manager = CommitAfterResponseManager()
		request.commit_after_response = callback_manager
		request.after_response.add(callback_manager.run)

	callback_manager.add(func)


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
