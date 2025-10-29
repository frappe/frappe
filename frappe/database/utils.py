# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
import string
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
