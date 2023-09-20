from collections.abc import Callable
from enum import Enum
from importlib import import_module
from typing import Any, get_type_hints

from pypika.queries import Column, QueryBuilder
from pypika.terms import PseudoColumn

import frappe
from frappe.query_builder.terms import NamedParameterWrapper

from .builder import MariaDB, Postgres


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


class ImportMapper:
	def __init__(self, func_map: dict[db_type_is, Callable]) -> None:
		self.func_map = func_map

	def __call__(self, *args: Any, **kwds: Any) -> Callable:
		db = db_type_is(frappe.conf.db_type or "mariadb")
		return self.func_map[db](*args, **kwds)


class BuilderIdentificationFailed(Exception):
	def __init__(self):
		super().__init__("Couldn't guess builder")


def get_query_builder(type_of_db: str) -> Postgres | MariaDB:
	"""[return the query builder object]

	Args:
	        type_of_db (str): [string value of the db used]

	Returns:
	        Query: [Query object]
	"""
	db = db_type_is(type_of_db)
	picks = {db_type_is.MARIADB: MariaDB, db_type_is.POSTGRES: Postgres}
	return picks[db]


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


def patch_query_execute():
	"""Patch the Query Builder with helper execute method
	This excludes the use of `frappe.db.sql` method while
	executing the query object
	"""

	def execute_query(query, *args, **kwargs):
		child_queries = query._child_queries if isinstance(query._child_queries, list) else []
		query, params = prepare_query(query)
		result = frappe.db.sql(query, params, *args, **kwargs)  # nosemgrep
		execute_child_queries(child_queries, result)
		return result

	def execute_child_queries(queries, result):
		if not result or not isinstance(result[0], dict) or not result[0].name:
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
		import inspect

		param_collector = NamedParameterWrapper()
		query = query.get_sql(param_wrapper=param_collector)
		if frappe.flags.in_safe_exec:
			from frappe.utils.safe_exec import check_safe_sql_query

			if not check_safe_sql_query(query, throw=False):
				callstack = inspect.stack()
				if len(callstack) >= 3 and ".py" in callstack[2].filename:
					# ignore any query builder methods called from python files
					# assumption is that those functions are whitelisted already.

					# since query objects are patched everywhere any query.run()
					# will have callstack like this:
					# frame0: this function prepare_query()
					# frame1: execute_query()
					# frame2: frame that called `query.run()`
					#
					# if frame2 is server script <serverscript> is set as the filename
					# it shouldn't be allowed.
					pass
				else:
					raise frappe.PermissionError("Only SELECT SQL allowed in scripting")
		return query, param_collector.get_parameters()

	builder_class = frappe.qb._BuilderClasss

	if not builder_class:
		raise BuilderIdentificationFailed

	builder_class.run = execute_query
	builder_class.walk = prepare_query
	frappe._qb_patched[frappe.conf.db_type] = True


def patch_query_aggregation():
	"""Patch aggregation functions to frappe.qb"""
	from frappe.query_builder.functions import _avg, _max, _min, _sum

	frappe.qb.max = _max
	frappe.qb.min = _min
	frappe.qb.avg = _avg
	frappe.qb.sum = _sum
	frappe._qb_patched[frappe.conf.db_type] = True
