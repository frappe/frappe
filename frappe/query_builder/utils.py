import inspect
from collections.abc import Callable
from enum import Enum
from importlib import import_module
from typing import Any, get_type_hints

from pypika.queries import Column, QueryBuilder, _SetOperation
from pypika.terms import PseudoColumn

import frappe
from frappe.query_builder.terms import NamedParameterWrapper

from .builder import Base, MariaDB, Postgres, SQLite


class PseudoColumnMapper(PseudoColumn):
	def __init__(self, name: str) -> None:
		super().__init__(name)

	def get_sql(self, **kwargs):
		if frappe.db.db_type == "postgres":
			self.name = self.name.replace("`", '"')
		return self.name


class db_type_is(Enum):
	MARIADB = "mariadb"
	POSTGRES = "postgres"
	SQLITE = "sqlite"


DB_TYPE_MAP = {
	db_type_is.MARIADB: MariaDB,
	db_type_is.POSTGRES: Postgres,
	db_type_is.SQLITE: SQLite,
}


class ImportMapper:
	def __init__(self, func_map: dict[db_type_is, Callable]) -> None:
		self.func_map = func_map

	def __call__(self, *args: Any, **kwds: Any) -> Callable:
		db = db_type_is(frappe.conf.db_type)
		return self.func_map[db](*args, **kwds)


class BuilderIdentificationFailed(Exception):
	def __init__(self):
		super().__init__("Couldn't guess builder")


def get_query_builder(type_of_db: str) -> Postgres | MariaDB | SQLite:
	"""Return the query builder object.

	Args:
	        type_of_db: string value of the db used
	"""
	return DB_TYPE_MAP[db_type_is(type_of_db)]


def get_query(*args, **kwargs) -> QueryBuilder:
	from frappe.database.query import Engine

	return Engine().get_query(*args, **kwargs)


def get_attr(method_string):
	modulename = ".".join(method_string.split(".")[:-1])
	methodname = method_string.split(".")[-1]
	return getattr(import_module(modulename), methodname)


def DocType(*args, **kwargs):
	return frappe.qb.DocType(*args, **kwargs)


def Table(*args, **kwargs):
	return frappe.qb.Table(*args, **kwargs)


def execute_query(query, *args, **kwargs):
	child_queries = query._child_queries
	query, params = prepare_query(query)
	result = frappe.local.db.sql(query, params, *args, **kwargs)  # nosemgrep

	if child_queries and isinstance(child_queries, list) and result:
		execute_child_queries(child_queries, result)

	return result


def execute_child_queries(queries, result):
	if not isinstance(result[0], dict) or not result[0].name:
		return
	parent_names = [d.name for d in result]
	for child_query in queries:
		data = child_query.get_query(parent_names).run(as_dict=1)
		for row in result:
			row[child_query.fieldname] = []
			for d in data:
				if str(d.parent) == str(row.name) and d.parentfield == child_query.fieldname:
					if "parent" not in child_query.fields:
						del d["parent"]
					if "parentfield" not in child_query.fields:
						del d["parentfield"]
					row[child_query.fieldname].append(d)


def prepare_query(query):
	param_collector = NamedParameterWrapper()
	query = query.get_sql(param_wrapper=param_collector)
	if frappe.local.flags.get("in_safe_exec", False):
		from frappe.utils.safe_exec import SERVER_SCRIPT_FILE_PREFIX, check_safe_sql_query

		if not check_safe_sql_query(query, throw=False):
			callstack = inspect.stack()

			# This check is required because QB can execute from anywhere and we can not
			# reliably provide a safe version for it in server scripts.

			# since query objects are patched everywhere any query.run()
			# will have callstack like this:
			# frame0: this function prepare_query()
			# frame1: execute_query()
			# frame2: frame that called `query.run()`
			#
			# if frame2 is server script <serverscript> is set as the filename it shouldn't be allowed.
			if len(callstack) >= 3 and SERVER_SCRIPT_FILE_PREFIX in callstack[2].filename:
				raise frappe.PermissionError("Only SELECT SQL allowed in scripting")

	return query, param_collector.parameters


def patch_query_execute():
	"""Patch the Query Builder with helper execute method
	This excludes the use of `frappe.db.sql` method while
	executing the query object
	"""

	QueryBuilder.run = execute_query
	QueryBuilder.walk = prepare_query

	# To support running union queries
	_SetOperation.run = execute_query
	_SetOperation.walk = prepare_query


def patch_query_aggregation():
	"""Patch aggregation functions to frappe.qb"""
	from frappe.query_builder.functions import _avg, _max, _min, _sum

	Base.max = _max
	Base.min = _min
	Base.avg = _avg
	Base.sum = _sum


def patch_get_query():
	Base.get_query = get_query


def patch_all():
	patch_query_execute()
	patch_query_aggregation()
	patch_get_query()
