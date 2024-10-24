# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from functools import cached_property, wraps

import frappe
from frappe.query_builder.builder import MariaDB, Postgres
from frappe.query_builder.functions import Function
from frappe.types import DocRef

Query = str | MariaDB | Postgres
QueryValues = tuple | list | dict | None
FilterValue = DocRef | str | int | bool

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


def convert_to_value(o: FilterValue):
	if hasattr(o, "__value__"):
		return o.__value__()
	if isinstance(o, bool):
		return int(o)
	return o


def is_query_type(query: str, query_type: str | tuple[str, ...]) -> bool:
	return query.lstrip().split(maxsplit=1)[0].lower().startswith(query_type)


def is_pypika_function_object(field: str) -> bool:
	return getattr(field, "__module__", None) == "pypika.functions" or isinstance(field, Function)


def get_doctype_name(table_name: str) -> str:
	if table_name.startswith(("tab", "`tab", '"tab')):
		table_name = table_name.replace("tab", "", 1)
	table_name = table_name.replace("`", "")
	return table_name.replace('"', "")


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
			if frappe.db.is_interface_error(e):
				frappe.db.connect()
				return func(*args, **kwargs)
			raise

	return wrapper
