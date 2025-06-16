# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
from collections.abc import Callable
from contextlib import contextmanager
from functools import cached_property, wraps

import frappe
from frappe.query_builder.builder import MariaDB, Postgres, SQLite
from frappe.query_builder.functions import Function

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


def convert_to_value(o: FilterValue):
	if isinstance(o, bool):
		return int(o)
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


def _should_execute_in_new_transaction() -> bool:
	"""Evaluate if the current request is a GET request and frappe.in_test is False"""

	request = getattr(frappe.local, "request", False)
	return request and request.method == "GET" and not frappe.in_test


@contextmanager
def execute_in_new_transaction(
	condition: Callable | bool = _should_execute_in_new_transaction, commit: bool = True
):
	"""
	Execute a block of code in new transaction, based on some condtion.
	By default, it will execute in a new transaction if the context is
	a GET request and frappe.in_test is False.

	This is useful when you want to commit something in an otherwise safe request
	or without affecting the current transaction.

	:param condition: A callable or boolean to determine if the block should be executed in a new transaction.
	:param commit: By default, the transaction will be committed after the block is executed.
		Set to False if you want to handle committing / rolling back the transaction manually.
	"""

	if callable(condition):
		condition = condition()

	if not condition:
		yield
		return

	original_db = frappe.local.db
	frappe.connect(set_admin_as_user=False)
	new_db = frappe.local.db

	try:
		yield
	finally:
		if commit:
			new_db.commit()

		new_db.close()
		frappe.local.db = original_db
